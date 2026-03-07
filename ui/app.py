import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from agent.graph import build_graph
from agent.privacy_middleware import PrivacyMiddleware
from agent.tools import init_tools
from privacy_layer.obfuscator import Obfuscator
from rag.indexer import EAIndexer
from rag.retriever import EARetriever
from ea_connector import writer_com

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
UI_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "ui_config.json")
CHROMA_DIR     = ".chromadb"
PENDING_ACTION_FILE = "pending_action.json"

# ---------------------------------------------------------------------------
# Helpers — persistent UI config
# ---------------------------------------------------------------------------
def load_ui_config() -> dict:
    if os.path.exists(UI_CONFIG_PATH):
        with open(UI_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"qeax_path": ""}

def save_ui_config(config: dict) -> None:
    with open(UI_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="EA AI Assistant",
    page_icon="🏗️",
    layout="wide",
)

st.title("🏗️ Sparx EA AI Assistant")
st.caption("Privacy-preserving AI assistant for Sparx Enterprise Architect")

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "ui_config" not in st.session_state:
    st.session_state.ui_config = load_ui_config()

if "agent_ready" not in st.session_state:
    st.session_state.agent_ready = False

if "index_loaded" not in st.session_state:
    st.session_state.index_loaded = False

# ---------------------------------------------------------------------------
# Agent initialization (once per session)
# ---------------------------------------------------------------------------
def init_agent():
    graph      = build_graph()
    middleware = PrivacyMiddleware(graph, enabled=True)
    obfuscator = middleware.obfuscator
    indexer    = EAIndexer(obfuscator, persist_directory=CHROMA_DIR)
    retriever  = EARetriever(indexer, obfuscator)

    st.session_state.middleware = middleware
    st.session_state.indexer    = indexer
    st.session_state.retriever  = retriever
    st.session_state.agent_ready = True

def run_reindex(qeax_path: str) -> str:
    """Runs full re-index and returns a status message."""
    indexer  = st.session_state.indexer
    retriever = st.session_state.retriever
    count = indexer.reindex_all(qeax_path)
    init_tools(retriever, qeax_path)
    st.session_state.index_loaded = True
    return f"✅ {count} elements indexed successfully."

if not st.session_state.agent_ready:
    with st.spinner("Initializing agent..."):
        init_agent()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:

    # ── Model path ──────────────────────────────────────────────────────────
    st.header("⚙️ Model Configuration")

    qeax_input = st.text_input(
        "Path to .qeax file",
        value=st.session_state.ui_config.get("qeax_path", ""),
        placeholder=r"C:\Users\...\model.qeax",
        help="Full path to the Sparx EA model file (.qeax).",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Save Path", use_container_width=True):
            st.session_state.ui_config["qeax_path"] = qeax_input
            save_ui_config(st.session_state.ui_config)
            st.success("Path saved.")

    with col2:
        update_clicked = st.button(
            "🔄 Update Data",
            use_container_width=True,
            help="Re-reads the entire EA model and rebuilds the vector index.",
        )

    if update_clicked:
        path = qeax_input.strip()
        if not path:
            st.error("Please enter a model path first.")
        elif not os.path.exists(path):
            st.error(f"File not found:\n{path}")
        else:
            with st.spinner("Re-indexing model..."):
                try:
                    msg = run_reindex(path)
                    st.success(msg)
                except Exception as e:
                    st.error(f"Indexing error:\n{e}")

    if st.session_state.index_loaded:
        st.caption("🟢 Index up to date")
    else:
        st.caption("🔴 No index loaded — click 'Update Data' to start.")

    st.divider()

    # ── Privacy Layer ────────────────────────────────────────────────────────
    st.header("🔒 Privacy Layer")

    middleware = st.session_state.middleware
    privacy_enabled = st.toggle(
        "Enabled",
        value=middleware.enabled,
        help="When enabled, element names are obfuscated before being sent to the LLM.",
    )
    middleware.enabled = privacy_enabled

    if privacy_enabled:
        st.caption("✅ Identifiers are obfuscated before reaching the LLM.")
    else:
        st.caption("⚠️ Real names are sent to the LLM directly.")

    st.metric("Mapped elements", middleware.obfuscator.element_count)

    st.divider()

    # ── Model search ─────────────────────────────────────────────────────────
    st.header("🔍 Model Search")

    if st.session_state.index_loaded:
        search_query = st.text_input(
            "Search model elements:",
            placeholder="e.g. safety block",
        )
        if search_query:
            results = st.session_state.retriever.hybrid_search(search_query, n_results=5)
            if results:
                for r in results:
                    real_name = middleware.obfuscator.deobfuscate(r["token"])
                    st.markdown(
                        f"**{real_name}** `{r['ea_type']}` "
                        f"— score: `{r['score']}` _{r['search_type']}_"
                    )
            else:
                st.caption("No results found.")
    else:
        st.caption("Load a model first to enable search.")

    st.divider()

    # ── Chat controls ────────────────────────────────────────────────────────
    if st.button("🗑️ Clear chat history", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------------------------
# Index-not-loaded warning in main area
# ---------------------------------------------------------------------------
if not st.session_state.index_loaded:
    st.warning(
        "⚠️ No EA model loaded. "
        "Please enter the model path in the sidebar and click **'Update Data'**.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# Chat history display
# ---------------------------------------------------------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---------------------------------------------------------------------------
# Chat input — THREE mutually exclusive branches
# ---------------------------------------------------------------------------
if prompt := st.chat_input(
    "Ask something about your EA model...",
    disabled=not st.session_state.get("index_loaded", True),
):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):

        # Mache den Input ganz sauber (entferne Punkte, Leerzeichen etc.)
        normalized = prompt.strip().lower().replace(".", "")

        # ── Branch 1: YES — execute cached action directly, SKIP AGENT ──
        if normalized in ("yes", "ja", "y"):
            if os.path.exists(PENDING_ACTION_FILE):
                with open(PENDING_ACTION_FILE, "r", encoding="utf-8") as f:
                    action = json.load(f)
                
                # Datei sofort löschen
                os.remove(PENDING_ACTION_FILE)
                
                with st.status("Executing action...", expanded=True) as status:
                    st.write(f"⚙️ Action: `{action['tool']}`")
                    try:
                        # De-obfuscate Werte, falls der Privacy-Layer aktiv ist
                        obs = st.session_state.middleware.obfuscator
                        def deobs(val): return obs.deobfuscate(val) if isinstance(val, str) else val

                        if action["tool"] == "create_element":
                            response = writer_com.create_element(
                                deobs(action["name"]), deobs(action["ea_type"]),
                                deobs(action["package_name"]), deobs(action["stereotype"]),
                                deobs(action.get("notes", ""))
                            )
                        elif action["tool"] == "update_notes":
                            response = writer_com.update_element_notes(
                                deobs(action["element_name"]), deobs(action["new_notes"])
                            )
                        elif action["tool"] == "set_tag":
                            response = writer_com.set_tagged_value(
                                deobs(action["element_name"]), deobs(action["tag_name"]),
                                deobs(action["tag_value"])
                            )
                        elif action["tool"] == "create_connector":
                            response = writer_com.create_connector(
                                deobs(action["source_name"]), deobs(action["target_name"]),
                                deobs(action["connector_type"]), deobs(action["stereotype"]),
                                deobs(action.get("name", ""))
                            )
                        else:
                            response = f"❌ Unknown action type: {action['tool']}"

                        response += "\n\n> 💡 Click **Update Data** in the sidebar to refresh the index."
                    except Exception as e:
                        response = f"❌ Error executing action: {e}"
                    status.update(label="Done!", state="complete", expanded=False)
            else:
                response = "⚠️ Nothing to confirm — no pending action found."

        # ── Branch 2: NO — cancel, skip agent ───────────────────────────
        elif normalized in ("no", "nein", "n"):
            if os.path.exists(PENDING_ACTION_FILE):
                os.remove(PENDING_ACTION_FILE)
            response = "Action cancelled."

        # ── Branch 3: everything else — normal agent flow ────────────────
        else:
            with st.status("Thinking...", expanded=True) as status:
                if middleware.enabled:
                    st.write("🔍 Privacy Layer enabled (identifiers are obfuscated).")
                    
                st.write("⚙️ Running AI Agent...")
                response = middleware.chat(prompt)
                
                status.update(label="Done!", state="complete", expanded=False)

        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
