import sqlite3
import pandas as pd
from langchain_core.tools import tool
from rag.retriever import EARetriever

# ---------------------------------------------------------------------------
# Module-level retriever — injected at startup via init_tools()
# ---------------------------------------------------------------------------
_retriever: EARetriever | None = None
_qeax_path: str | None = None


def init_tools(retriever: EARetriever, qeax_path: str) -> None:
    """
    Must be called once at app startup before any tool is invoked.
    Injects the live retriever and model path into the tools module.
    """
    global _retriever, _qeax_path
    _retriever = retriever
    _qeax_path = qeax_path


def _get_retriever() -> EARetriever:
    if _retriever is None:
        raise RuntimeError("Tools not initialized — call init_tools() first.")
    return _retriever


def _query_db(sql: str) -> list[dict]:
    """Executes a read-only SELECT on the .qeax SQLite file."""
    if _qeax_path is None:
        raise RuntimeError("Tools not initialized — call init_tools() first.")
    con = sqlite3.connect(f"file:{_qeax_path}?mode=ro", uri=True)
    try:
        df = pd.read_sql(sql, con)
        return df.to_dict(orient="records")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_model(query: str) -> str:
    """
    Semantically searches the EA model for elements relevant to the query.
    Use this as the primary tool for any question about model contents,
    elements, blocks, requirements, packages, or relationships.

    Args:
        query: Natural language question or keyword, e.g.
               'Welche Blöcke gibt es im PowerSystem?'
    """
    return _get_retriever().build_context_for_llm(query, n_results=7)


@tool
def get_element_details(name: str) -> str:
    """
    Returns detailed information about a specific EA element by its real name,
    including tagged values, connectors, package path, and stereotype.

    Args:
        name: The real element name as it appears in the EA model,
              e.g. 'BatteryManagementSystem'.
    """
    results = _query_db(f"""
        SELECT
            o.Object_ID, o.Object_Type, o.Name, o.Stereotype, o.Note AS Notes,
            p.Name AS PackageName
        FROM t_object o
        LEFT JOIN t_package p ON o.Package_ID = p.Package_ID
        WHERE o.Name LIKE '%{name}%'
        LIMIT 5
    """)

    if not results:
        return f"Kein Element mit dem Namen '{name}' gefunden."

    lines = []
    for r in results:
        oid = r["Object_ID"]

        # Tagged Values — empty values filtered via model_config values
        tags = _query_db(f"""
            SELECT Property AS name, Value FROM t_objectproperties
            WHERE Object_ID = {oid}
            AND Value IS NOT NULL
            AND Value != ''
            AND Value != 'None'
            AND Value != '<memo>'
        """)
        tag_str = " | ".join(f"{t['name']}={t['Value']}" for t in tags) or "–"

        # Connectors — NoteLinks excluded (Note text already in chunk)
        cons = _query_db(f"""
            SELECT c.Connector_Type, c.Name,
                   src.Name AS SourceName, tgt.Name AS TargetName
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

        # Diagrams this element appears in
        diags = _query_db(f"""
            SELECT d.Name AS DiagramName
            FROM t_diagramobjects do
            JOIN t_diagram d ON do.Diagram_ID = d.Diagram_ID
            WHERE do.Object_ID = {oid}
        """)
        diag_str = ", ".join(d["DiagramName"] for d in diags) or "–"

        lines.append(
            f"[{r['Object_Type']}] {r['Name']} «{r['Stereotype'] or ''}»\n"
            f"  Paket:         {r['PackageName']}\n"
            f"  Beschreibung:  {r['Notes'] or '–'}\n"
            f"  Tagged Values: {tag_str}\n"
            f"  Verbindungen:  {con_str}\n"
            f"  Diagramme:     {diag_str}"
        )

    return "\n\n".join(lines)


@tool
def get_package_contents(package_name: str) -> str:
    """
    Returns all elements and sub-packages within a given package.

    Args:
        package_name: The real package name, e.g. 'PowerSystem'.
    """
    results = _query_db(f"""
        SELECT o.Object_Type, o.Name, o.Stereotype
        FROM t_object o
        JOIN t_package p ON o.Package_ID = p.Package_ID
        WHERE p.Name LIKE '%{package_name}%'
        ORDER BY o.Object_Type, o.Name
    """)

    if not results:
        return f"Kein Paket mit dem Namen '{package_name}' gefunden."

    lines = [f"Inhalt von Paket '{package_name}':\n"]
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
        query: A valid SQL SELECT statement, e.g.
               'SELECT Name, Object_Type FROM t_object WHERE Stereotype = "block"'
    """
    if not query.strip().upper().startswith("SELECT"):
        return "Fehler: Nur SELECT-Abfragen sind erlaubt."

    try:
        results = _query_db(query)
        if not results:
            return "Abfrage erfolgreich, aber keine Ergebnisse."
        lines = [str(r) for r in results[:50]]  # max 50 Zeilen
        return "\n".join(lines)
    except Exception as e:
        return f"SQL-Fehler: {e}"
