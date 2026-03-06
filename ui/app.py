import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from agent.graph import build_graph
from agent.privacy_middleware import PrivacyMiddleware
from rag.indexer import EAIndexer
from rag.retriever import EARetriever

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

if "middleware" not in st.session_state:
    with st.spinner("Initializing agent..."):
        graph = build_graph()
        middleware = PrivacyMiddleware(graph)

        # Pre-register mock identifiers — replace with real EA data in Phase 5
        middleware.register_identifiers({
            "DriveControlModule_V4": "element",
            "BatteryManagementSystem": "element",
            "SafetyMonitor": "element",
            "PowerRequirement_01": "element",
            "PowerSystem": "package",
            "SafetySystem": "package",
        })
        st.session_state.middleware = middleware

if "indexer" not in st.session_state:
    with st.spinner("Loading vector index..."):
        from privacy_layer.obfuscator import Obfuscator
        obs = st.session_state.middleware.obfuscator
        indexer = EAIndexer(obs, persist_directory=".chromadb")
        retriever = EARetriever(indexer, obs)

        # Index mock elements — replace with real EA data in Phase 5
        mock_elements = [
            {"real_name": "DriveControlModule_V4", "kind": "element",
             "ea_type": "Block", "stereotype": "SysML1.4::block",
             "parent_path": "PowerSystem", "description": "Controls drive output"},
            {"real_name": "BatteryManagementSystem", "kind": "element",
             "ea_type": "Block", "stereotype": "SysML1.4::block",
             "parent_path": "PowerSystem", "description": "Manages battery charging cycles"},
            {"real_name": "SafetyMonitor", "kind": "element",
             "ea_type": "Block", "stereotype": "SysML1.4::block",
             "parent_path": "SafetySystem", "description": "Monitors safety-critical signals"},
            {"real_name": "PowerRequirement_01", "kind": "element",
             "ea_type": "Requirement", "stereotype": "",
             "parent_path": "SafetySystem", "description": "System shall supply 48V nominal"},
        ]
        indexer.index_elements(mock_elements)
        st.session_state.indexer = indexer
        st.session_state.retriever = retriever

# ---------------------------------------------------------------------------
# Sidebar — model info & session controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Session Info")
    middleware = st.session_state.middleware
    st.metric("Registered identifiers", middleware.obfuscator.mapping_size)

    st.divider()
    st.header("RAG Search")
    search_query = st.text_input("Search model elements:", placeholder="e.g. safety block")
    if search_query:
        results = st.session_state.retriever.hybrid_search(search_query, n_results=5)
        for r in results:
            real_name = middleware.obfuscator.deobfuscate(r["token"])
            st.markdown(f"**{real_name}** `{r['ea_type']}` — score: `{r['score']}`")

    st.divider()
    if st.button("🗑️ Clear chat history"):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------------------------
# Chat history display
# ---------------------------------------------------------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---------------------------------------------------------------------------
# Chat input & agent response
# ---------------------------------------------------------------------------
if prompt := st.chat_input("Ask something about your EA model..."):

    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Agent response with live status updates
    with st.chat_message("assistant"):
        with st.status("Thinking...", expanded=True) as status:
            st.write("🔍 Obfuscating input through privacy layer...")
            obfuscated = st.session_state.middleware.translator.obfuscate_text(prompt)
            st.write(f"📤 Sending to LLM: `{obfuscated[:120]}...`" if len(obfuscated) > 120 else f"📤 Sending to LLM: `{obfuscated}`")
            st.write("⚙️ Running ReAct agent...")
            response = st.session_state.middleware.chat(prompt)
            st.write("🔓 Deobfuscating response...")
            status.update(label="Done!", state="complete", expanded=False)

        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
