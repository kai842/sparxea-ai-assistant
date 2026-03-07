import sqlite3
import pandas as pd
import json
import os
from langchain_core.tools import tool
from rag.retriever import EARetriever
from ea_connector import writer_com

# ---------------------------------------------------------------------------
# Module-level retriever & config
# ---------------------------------------------------------------------------
_retriever: EARetriever | None = None
_qeax_path: str | None = None

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

# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@tool
def search_model(query: str) -> str:
    """Semantically searches the EA model for elements relevant to the query."""
    return _get_retriever().build_context_for_llm(query, n_results=7)

@tool
def get_element_details(name: str) -> str:
    """Returns detailed information about a specific EA element."""
    results = _query_db(f"""
        SELECT o.Object_ID, o.Object_Type, o.Name, o.Stereotype, o.Note AS Notes, p.Name AS PackageName
        FROM t_object o
        LEFT JOIN t_package p ON o.Package_ID = p.Package_ID
        WHERE o.Name LIKE '%{name}%' LIMIT 5
    """)
    if not results: return f"No element found with name '{name}'."
    lines = []
    for r in results:
        oid = r["Object_ID"]
        tags = _query_db(f"SELECT Property AS name, Value FROM t_objectproperties WHERE Object_ID = {oid}")
        tag_str = " | ".join(f"{t['name']}={t['Value']}" for t in tags) or "–"
        cons = _query_db(f"""
            SELECT c.Connector_Type, src.Name AS SourceName, tgt.Name AS TargetName
            FROM t_connector c
            JOIN t_object src ON c.Start_Object_ID = src.Object_ID
            JOIN t_object tgt ON c.End_Object_ID = tgt.Object_ID
            WHERE (c.Start_Object_ID = {oid} OR c.End_Object_ID = {oid}) AND c.Connector_Type != 'NoteLink'
        """)
        con_str = " | ".join(f"{c['SourceName']} →[{c['Connector_Type']}]→ {c['TargetName']}" for c in cons) or "–"
        lines.append(f"[{r['Object_Type']}] {r['Name']} «{r['Stereotype'] or ''}»\n  Package: {r['PackageName']}\n  Notes: {r['Notes']}\n  Tags: {tag_str}\n  Connectors: {con_str}")
    return "\n\n".join(lines)

@tool
def get_package_contents(package_name: str) -> str:
    """Returns all elements and sub-packages within a given package."""
    results = _query_db(f"SELECT Object_Type, Name, Stereotype FROM t_object o JOIN t_package p ON o.Package_ID = p.Package_ID WHERE p.Name LIKE '%{package_name}%'")
    if not results: return f"No package found with name '{package_name}'."
    return "\n".join([f"[{r['Object_Type']}] {r['Name']} «{r['Stereotype']}»" for r in results])

@tool
def run_sql_query(query: str) -> str:
    """Executes a read-only SQL SELECT query directly on the EA database."""
    if not query.strip().upper().startswith("SELECT"): return "Error: Only SELECT permitted."
    try:
        results = _query_db(query)
        return "\n".join([str(r) for r in results[:50]]) if results else "Query successful, no results."
    except Exception as e: return f"SQL error: {e}"

# ---------------------------------------------------------------------------
# Write tools (JSON File Cache)
# ---------------------------------------------------------------------------

@tool
def create_element_in_model(name: str, ea_type: str, package_name: str, stereotype: str = "", notes: str = "") -> str:
    """Prepares the creation of a new element. Call this tool to stage the action."""
    action = {"tool": "create_element", "name": name, "ea_type": ea_type, "package_name": package_name, "stereotype": stereotype, "notes": notes}
    with open(PENDING_ACTION_FILE, "w", encoding="utf-8") as f: json.dump(action, f)
    return f"SUCCESS. Tell the user exactly: 'Planned: Create [{ea_type}] {name} in {package_name}. Please reply with **yes** to confirm.'"

@tool
def update_element_notes_in_model(element_name: str, new_notes: str) -> str:
    """Prepares updating the notes of an EA element."""
    action = {"tool": "update_notes", "element_name": element_name, "new_notes": new_notes}
    with open(PENDING_ACTION_FILE, "w", encoding="utf-8") as f: json.dump(action, f)
    return "SUCCESS. Tell the user to reply with 'yes' to confirm."

@tool
def set_tagged_value_in_model(element_name: str, tag_name: str, tag_value: str) -> str:
    """Prepares setting a Tagged Value on an EA element."""
    action = {"tool": "set_tag", "element_name": element_name, "tag_name": tag_name, "tag_value": tag_value}
    with open(PENDING_ACTION_FILE, "w", encoding="utf-8") as f: json.dump(action, f)
    return "SUCCESS. Tell the user to reply with 'yes' to confirm."

@tool
def create_connector_in_model(source_name: str, target_name: str, connector_type: str, stereotype: str = "", name: str = "") -> str:
    """Prepares creating a connector between two EA elements."""
    action = {"tool": "create_connector", "source_name": source_name, "target_name": target_name, "connector_type": connector_type, "stereotype": stereotype, "name": name}
    with open(PENDING_ACTION_FILE, "w", encoding="utf-8") as f: json.dump(action, f)
    return "SUCCESS. Tell the user to reply with 'yes' to confirm."
