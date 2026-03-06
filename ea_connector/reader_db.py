import sqlite3
import pandas as pd
from pathlib import Path
from ea_connector.model_config import TABLES


def read_model_from_db(qeax_path: str) -> dict[str, pd.DataFrame]:
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
        data = {}
        for table_key, sql in TABLES.items():
            try:
                data[table_key] = pd.read_sql(sql, con)
            except Exception as e:
                print(f"   ⚠️  Skipping '{table_key}': {e}")
                data[table_key] = pd.DataFrame()
    finally:
        con.close()

    _log_summary(data)
    return data


def _log_summary(data: dict[str, pd.DataFrame]) -> None:
    print("✅ Model read successfully:")
    for key, df in data.items():
        print(f"   {key:<20} {len(df):>6} rows")


def build_package_path(packages_df: pd.DataFrame) -> dict[int, str]:
    id_to_name   = dict(zip(packages_df["Package_ID"], packages_df["Name"]))
    id_to_parent = dict(zip(packages_df["Package_ID"], packages_df["Parent_ID"]))

    def get_path(pkg_id: int) -> str:
        parts, current, visited = [], pkg_id, set()
        while current and current not in visited:
            visited.add(current)
            name = id_to_name.get(current)
            if name:
                parts.append(name)
            current = id_to_parent.get(current)
        return " > ".join(reversed(parts))

    return {pkg_id: get_path(pkg_id) for pkg_id in packages_df["Package_ID"]}
