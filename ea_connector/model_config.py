# ea_connector/model_config.py

# ---------------------------------------------------------------------------
# Tables to read from the .qeax SQLite file
# Add or remove tables here to control what gets loaded into DataFrames.
# ---------------------------------------------------------------------------
TABLES = {
    "objects": """
        SELECT
            Object_ID, Object_Type, Name, Alias,
            Package_ID, Note AS Notes, Stereotype, ea_guid AS GUID
        FROM t_object
        WHERE Object_Type NOT IN ('Boundary')
    """,

    "packages": """
        SELECT Package_ID, Name, Parent_ID, ea_guid AS GUID, Notes
        FROM t_package
    """,

    "connectors": """
        SELECT
            Connector_ID, ea_guid AS GUID,
            Connector_Type AS Type, SubType, Name, Direction, Notes,
            Start_Object_ID AS ClientID, End_Object_ID AS SupplierID,
            Stereotype
        FROM t_connector
    """,

    "tagged_values": """
        SELECT PropertyID, Object_ID, Property AS Name, Value
        FROM t_objectproperties
    """,

    "diagrams": """
        SELECT Diagram_ID, Name, Diagram_Type AS Type, Package_ID, Notes
        FROM t_diagram
    """,

    # Uncomment to load diagram membership per element:
    "diagram_objects": """
        SELECT Diagram_ID, Object_ID
        FROM t_diagramobjects
    """,
}

# ---------------------------------------------------------------------------
# Element types to exclude entirely from indexing
# These are pure layout/visual elements with no semantic content.
# ---------------------------------------------------------------------------
EXCLUDED_ELEMENT_TYPES = {
    "Boundary",   # visual grouping box
    "Text",       # free-floating text box (no semantic links)
}

# ---------------------------------------------------------------------------
# Note element types — their text gets appended to linked elements' chunks.
# NoteLinks are not filtered; instead Note content enriches the target chunk.
# ---------------------------------------------------------------------------
NOTE_ELEMENT_TYPES = {"Note"}

# ---------------------------------------------------------------------------
# Connector types to exclude from the connector display in tool output.
# Note: NoteLinks are NOT excluded — their content is resolved separately.
# ---------------------------------------------------------------------------
EXCLUDED_CONNECTOR_TYPES: set[str] = set()  # e.g. {"Realisation"} if needed

# ---------------------------------------------------------------------------
# Tagged Value filters — values matching these are considered empty.
# ---------------------------------------------------------------------------
EMPTY_TAG_VALUES = {None, "", "None", "<memo>"}

# ---------------------------------------------------------------------------
# Chunk builder settings
# ---------------------------------------------------------------------------
MAX_CONNECTORS_PER_CHUNK = 10   # avoid bloated chunks for highly connected elements
MAX_TAGS_PER_CHUNK       = 15
