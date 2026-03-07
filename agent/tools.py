import sqlite3
import pandas as pd
import json
import os
import threading
from langchain_core.tools import tool
from rag.retriever import EARetriever
from ea_connector import writer_com

# ---------------------------------------------------------------------------
# Module-level retriever & config
# ---------------------------------------------------------------------------
_retriever: EARetriever | None = None
_qeax_path: str | None = None

_file_lock = threading.Lock()

PENDING_ACTION_FILE = "pending_action.json"


def init_tools(retriever: EARetriever, qeax_path: str) -> None:
    global _retriever, _qeax_path
    _retriever = retriever
    _qeax_path = qeax_path


def _get_retriever() -> EARetriever:
    if _retriever is None:
        raise RuntimeError("Tools not initialized — call init_tools() first.")
    return _retriever


def _query_db(sql: str) -> list[dict]:
    if _qeax_path is None:
        raise RuntimeError("Tools not initialized — call init_tools() first.")
    con = sqlite3.connect(f"file:{_qeax_path}?mode=ro", uri=True)
    try:
        df = pd.read_sql(sql, con)
        return df.to_dict(orient="records")
    finally:
        con.close()


def _append_action(action: dict) -> list:
    """
    Appends a new action to the pending actions list.
    Thread-safe via lock — prevents race conditions during parallel tool calls.
    """
    with _file_lock:
        # Read existing actions
        if os.path.exists(PENDING_ACTION_FILE):
            try:
                with open(PENDING_ACTION_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    actions = json.loads(content) if content else []
            except (json.JSONDecodeError, OSError):
                actions = []
        else:
            actions = []

        # Append and write back
        actions.append(action)
        with open(PENDING_ACTION_FILE, "w", encoding="utf-8") as f:
            json.dump(actions, f, indent=2)

    return actions


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@tool
def search_model(query: str) -> str:
    """
    Semantically searches the EA model for elements relevant to the query.
    Use this as the primary tool for any question about model contents,
    elements, blocks, requirements, packages, or relationships.

    Args:
        query: Natural language question or keyword, e.g.
               'Which blocks exist in the model?'
    """
    return _get_retriever().build_context_for_llm(query, n_results=7)


@tool
def get_element_details(name: str) -> str:
    """
    Returns detailed information about a specific EA element by its real name,
    including tagged values, connectors, package path, and stereotype.

    Args:
        name: The real element name as it appears in the EA model,
              e.g. 'Block A'.
    """
    results = _query_db(f"""
        SELECT o.Object_ID, o.Object_Type, o.Name, o.Stereotype, o.Note AS Notes,
               p.Name AS PackageName
        FROM t_object o
        LEFT JOIN t_package p ON o.Package_ID = p.Package_ID
        WHERE o.Name LIKE '%{name}%' LIMIT 5
    """)

    if not results:
        return f"No element found with name '{name}'."

    lines = []
    for r in results:
        oid = r["Object_ID"]

        tags = _query_db(f"""
            SELECT Property AS name, Value FROM t_objectproperties
            WHERE Object_ID = {oid}
            AND Value IS NOT NULL AND Value != '' AND Value != 'None' AND Value != '<memo>'
        """)
        tag_str = " | ".join(f"{t['name']}={t['Value']}" for t in tags) or "–"

        cons = _query_db(f"""
            SELECT c.Connector_Type, src.Name AS SourceName, tgt.Name AS TargetName
            FROM t_connector c
            JOIN t_object src ON c.Start_Object_ID = src.Object_ID
            JOIN t_object tgt ON c.End_Object_ID   = tgt.Object_ID
            WHERE (c.Start_Object_ID = {oid} OR c.End_Object_ID = {oid})
            AND c.Connector_Type != 'NoteLink'
        """)
        con_str = " | ".join(
            f"{c['SourceName']} →[{c['Connector_Type']}]→ {c['TargetName']}"
            for c in cons
        ) or "–"

        diags = _query_db(f"""
            SELECT d.Name AS DiagramName
            FROM t_diagramobjects do
            JOIN t_diagram d ON do.Diagram_ID = d.Diagram_ID
            WHERE do.Object_ID = {oid}
        """)
        diag_str = ", ".join(d["DiagramName"] for d in diags) or "–"

        lines.append(
            f"[{r['Object_Type']}] {r['Name']} «{r['Stereotype'] or ''}»\n"
            f"  Package:       {r['PackageName']}\n"
            f"  Description:   {r['Notes'] or '–'}\n"
            f"  Tagged Values: {tag_str}\n"
            f"  Connectors:    {con_str}\n"
            f"  Diagrams:      {diag_str}"
        )

    return "\n\n".join(lines)


@tool
def get_package_contents(package_name: str) -> str:
    """
    Returns all elements and sub-packages within a given package.

    Args:
        package_name: The real package name, e.g. 'Blocks'.
    """
    results = _query_db(f"""
        SELECT o.Object_Type, o.Name, o.Stereotype
        FROM t_object o
        JOIN t_package p ON o.Package_ID = p.Package_ID
        WHERE p.Name LIKE '%{package_name}%'
        ORDER BY o.Object_Type, o.Name
    """)

    if not results:
        return f"No package found with name '{package_name}'."

    lines = [f"Contents of package '{package_name}':\n"]
    for r in results:
        stereo = f" «{r['Stereotype']}»" if r["Stereotype"] else ""
        lines.append(f"  [{r['Object_Type']}] {r['Name']}{stereo}")

    return "\n".join(lines)


@tool
def run_sql_query(query: str) -> str:
    """
    Executes a read-only SQL SELECT query directly on the EA model database.
    Use this for complex structural queries that span multiple tables.
    Only SELECT statements are permitted.

    Available tables: t_object, t_package, t_connector,
                      t_objectproperties, t_diagram, t_diagramobjects

    Args:
        query: A valid SQL SELECT statement.
    """
    if not query.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are permitted."
    try:
        results = _query_db(query)
        if not results:
            return "Query executed successfully, but returned no results."
        return "\n".join([str(r) for r in results[:50]])
    except Exception as e:
        return f"SQL error: {e}"


# ---------------------------------------------------------------------------
# Write tools — all use JSON file cache for thread-safety
# ---------------------------------------------------------------------------

@tool
def create_element_in_model(
    name: str,
    ea_type: str,
    package_name: str,
    stereotype: str = "",
    notes: str = "",
) -> str:
    """
    Stages the creation of a new element or package in the EA model.
    Call this tool once per element. Can be called multiple times to
    build a batch of actions. The user confirms all staged actions at once.

    Args:
        name:         Element name, e.g. 'MotorController'
        ea_type:      EA type, e.g. 'Class', 'Component', 'Requirement', 'Package'
        package_name: Target package name, e.g. 'Blocks'
        stereotype:   Optional stereotype, e.g. 'block'
        notes:        Optional description
    """
    action = {
        "tool": "create_element",
        "name": name,
        "ea_type": ea_type,
        "package_name": package_name,
        "stereotype": stereotype,
        "notes": notes,
    }
    actions = _append_action(action)
    return (
        f"SUCCESS. Action #{len(actions)} staged: "
        f"Create [{ea_type}] '{name}' in '{package_name}'. "
        f"Continue staging more actions or tell the user to confirm with 'yes'."
    )


@tool
def update_element_notes_in_model(element_name: str, new_notes: str) -> str:
    """
    Stages updating the notes/description of an existing EA element.

    Args:
        element_name: Exact element name as in the EA model
        new_notes:    New description text
    """
    action = {
        "tool": "update_notes",
        "element_name": element_name,
        "new_notes": new_notes,
    }
    actions = _append_action(action)
    return (
        f"SUCCESS. Action #{len(actions)} staged: "
        f"Update notes of '{element_name}'. "
        f"Continue staging more actions or tell the user to confirm with 'yes'."
    )


@tool
def set_tagged_value_in_model(
    element_name: str,
    tag_name: str,
    tag_value: str,
) -> str:
    """
    Stages setting or updating a Tagged Value on an existing EA element.

    Args:
        element_name: Exact element name
        tag_name:     Tagged Value name, e.g. 'status'
        tag_value:    New value, e.g. 'approved'
    """
    action = {
        "tool": "set_tag",
        "element_name": element_name,
        "tag_name": tag_name,
        "tag_value": tag_value,
    }
    actions = _append_action(action)
    return (
        f"SUCCESS. Action #{len(actions)} staged: "
        f"Set tag '{tag_name}={tag_value}' on '{element_name}'. "
        f"Continue staging more actions or tell the user to confirm with 'yes'."
    )


@tool
def create_connector_in_model(
    source_name: str,
    target_name: str,
    connector_type: str,
    stereotype: str = "",
    name: str = "",
) -> str:
    """
    Stages creating a connector between two existing EA elements.

    Args:
        source_name:    Name of the source element
        target_name:    Name of the target element
        connector_type: EA connector type, e.g. 'Association', 'Dependency'
        stereotype:     Optional stereotype
        name:           Optional connector label
    """
    action = {
        "tool": "create_connector",
        "source_name": source_name,
        "target_name": target_name,
        "connector_type": connector_type,
        "stereotype": stereotype,
        "name": name,
    }
    actions = _append_action(action)
    return (
        f"SUCCESS. Action #{len(actions)} staged: "
        f"Connect '{source_name}' →[{connector_type}]→ '{target_name}'. "
        f"Continue staging more actions or tell the user to confirm with 'yes'."
    )
