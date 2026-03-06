from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Mock data — simulates EA repository content without a real EA connection.
# Replace return values with real ea_connector calls in Phase 5.
# ---------------------------------------------------------------------------

MOCK_ELEMENTS = {
    "ELEMENT_001": {"name": "DriveControlModule_V4", "type": "Block", "stereotype": "SysML1.4::block"},
    "ELEMENT_002": {"name": "BatteryManagementSystem", "type": "Block", "stereotype": "SysML1.4::block"},
    "ELEMENT_003": {"name": "SafetyMonitor", "type": "Block", "stereotype": "SysML1.4::block"},
    "ELEMENT_004": {"name": "PowerRequirement_01", "type": "Requirement", "stereotype": ""},
}

MOCK_CONNECTORS = [
    {"id": "CONNECTOR_001", "source": "ELEMENT_001", "target": "ELEMENT_002", "type": "Association"},
    {"id": "CONNECTOR_002", "source": "ELEMENT_003", "target": "ELEMENT_001", "type": "Dependency"},
]

MOCK_PACKAGES = {
    "PACKAGE_001": {"name": "PowerSystem", "children": ["ELEMENT_001", "ELEMENT_002"]},
    "PACKAGE_002": {"name": "SafetySystem", "children": ["ELEMENT_003", "ELEMENT_004"]},
}


@tool
def get_all_elements() -> list[dict]:
    """
    Returns a list of all elements in the EA repository.
    Each entry contains the obfuscated token, element type, and stereotype.
    Use this to get an overview of the model contents.
    """
    return [
        {"token": k, "type": v["type"], "stereotype": v["stereotype"]}
        for k, v in MOCK_ELEMENTS.items()
    ]


@tool
def get_element_details(token: str) -> dict:
    """
    Returns detailed information about a specific element by its token.
    Use this when you need to inspect a particular element.

    Args:
        token: The obfuscated element token, e.g. 'ELEMENT_001'.
    """
    if token not in MOCK_ELEMENTS:
        return {"error": f"Element '{token}' not found."}
    return {"token": token, **MOCK_ELEMENTS[token]}


@tool
def get_connectors_for_element(token: str) -> list[dict]:
    """
    Returns all connectors (relationships) where the given element
    is either source or target.

    Args:
        token: The obfuscated element token, e.g. 'ELEMENT_001'.
    """
    result = [
        c for c in MOCK_CONNECTORS
        if c["source"] == token or c["target"] == token
    ]
    if not result:
        return [{"info": f"No connectors found for '{token}'."}]
    return result


@tool
def get_package_contents(token: str) -> dict:
    """
    Returns the contents (child element tokens) of a given package.

    Args:
        token: The obfuscated package token, e.g. 'PACKAGE_001'.
    """
    if token not in MOCK_PACKAGES:
        return {"error": f"Package '{token}' not found."}
    return {"token": token, **MOCK_PACKAGES[token]}


@tool
def run_sql_query(query: str) -> list[dict]:
    """
    Executes a read-only SQL query on the EA repository database.
    Only SELECT statements are permitted.
    Use this for complex queries that span multiple tables.

    Args:
        query: A valid SQL SELECT statement targeting EA tables
               (e.g. t_object, t_connector, t_package).
    """
    if not query.strip().upper().startswith("SELECT"):
        return [{"error": "Only SELECT queries are permitted."}]
    # Mock response — real implementation queries SQLite in Phase 5
    return [{"mock": "SQL query received", "query": query}]
