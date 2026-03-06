import sqlite3
import pandas as pd
from pathlib import Path


def read_model_from_db(qeax_path: str) -> dict[str, pd.DataFrame]:
    """
    Fast bulk read directly from a Sparx EA .qeax (SQLite) file.
    Opens the file in read-only mode — safe to use while EA is open.

    Returns a dict of DataFrames:
        - objects       : t_object       (all elements)
        - packages      : t_package      (package hierarchy)
        - connectors    : t_connector    (relationships)
        - tagged_values : t_objectproperties (tagged values)
        - diagrams      : t_diagram      (diagrams)
    """
    path = Path(qeax_path)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {qeax_path}")

    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            f"Cannot open model file: {path}\n"
            "Make sure the path is correct. If EA has an exclusive lock, "
            "close EA or work with a copy of the file."
        ) from e

    try:
        data = {
            "objects": pd.read_sql("""
                SELECT
                    Object_ID,
                    Object_Type,
                    Name,
                    Alias,
                    Package_ID,
                    Note        AS Notes,
                    Stereotype,
                    ea_guid     AS GUID
                FROM t_object
                WHERE Object_Type NOT IN ('Text', 'Note', 'Boundary')
            """, con),

            "packages": pd.read_sql("""
                SELECT
                    Package_ID,
                    Name,
                    Parent_ID,
                    ea_guid     AS GUID,
                    Notes
                FROM t_package
            """, con),

            "connectors": pd.read_sql("""
                SELECT
                    Connector_ID,
                    ea_guid         AS GUID,
                    Connector_Type  AS Type,
                    SubType,
                    Name,
                    Direction,
                    Notes,
                    Start_Object_ID AS ClientID,
                    End_Object_ID   AS SupplierID,
                    Stereotype
                FROM t_connector
            """, con),

            "tagged_values": pd.read_sql("""
                SELECT
                    PropertyID,
                    Object_ID,
                    Property    AS Name,
                    Value
                FROM t_objectproperties
            """, con),

            "diagrams": pd.read_sql("""
                SELECT
                    Diagram_ID,
                    Name,
                    Diagram_Type    AS Type,
                    Package_ID,
                    Notes
                FROM t_diagram
            """, con),
        }
    finally:
        con.close()

    _log_summary(data)
    return data


def _log_summary(data: dict[str, pd.DataFrame]) -> None:
    """Prints a quick summary of what was read."""
    print("✅ Model read successfully:")
    for key, df in data.items():
        print(f"   {key:<20} {len(df):>6} rows")


def build_package_path(packages_df: pd.DataFrame) -> dict[int, str]:
    """
    Builds a lookup dict: Package_ID → full path string.
    Example: {42: "Model > Backend > Services"}

    Useful for enriching element chunks with their full package hierarchy.
    """
    id_to_name = dict(zip(packages_df["Package_ID"], packages_df["Name"]))
    id_to_parent = dict(zip(packages_df["Package_ID"], packages_df["Parent_ID"]))

    def get_path(pkg_id: int) -> str:
        parts = []
        current = pkg_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            name = id_to_name.get(current)
            if name:
                parts.append(name)
            current = id_to_parent.get(current)
        return " > ".join(reversed(parts))

    return {pkg_id: get_path(pkg_id) for pkg_id in packages_df["Package_ID"]}
