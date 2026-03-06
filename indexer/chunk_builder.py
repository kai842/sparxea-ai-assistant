import pandas as pd
from ea_connector.reader_db import build_package_path


def build_chunks(data: dict[str, pd.DataFrame]) -> list[dict]:
    """
    Builds enriched text chunks from raw EA DataFrames.
    Each chunk represents one element or package, ready for embedding.
    """
    objects        = data["objects"]
    packages       = data["packages"]
    connectors     = data["connectors"]
    tagged_values  = data["tagged_values"]

    pkg_paths      = build_package_path(packages)
    tv_lookup      = _build_tv_lookup(tagged_values)
    con_lookup     = _build_connector_lookup(connectors, objects)

    chunks = []
    for _, row in objects.iterrows():
        chunk = _build_element_chunk(row, pkg_paths, tv_lookup, con_lookup)
        chunks.append(chunk)

    return chunks


def _build_tv_lookup(tagged_values: pd.DataFrame) -> dict[int, list[str]]:
    """Returns {Object_ID: ["key=value", ...]}"""
    lookup = {}
    for _, row in tagged_values.iterrows():
        oid = row["Object_ID"]
        if oid not in lookup:
            lookup[oid] = []
        lookup[oid].append(f"{row['Name']}={row['Value']}")
    return lookup


def _build_connector_lookup(
    connectors: pd.DataFrame, objects: pd.DataFrame
) -> dict[int, list[str]]:
    """Returns {Object_ID: ["→ TargetName (Type)", ...]}"""
    id_to_name = dict(zip(objects["Object_ID"], objects["Name"]))
    lookup = {}

    for _, con in connectors.iterrows():
        client_id   = con["ClientID"]
        supplier_id = con["SupplierID"]
        con_type    = con["Type"] or ""
        con_name    = con["Name"] or ""
        label       = f"{con_name} ({con_type})" if con_name else con_type

        # Outgoing from client
        target_name = id_to_name.get(supplier_id, f"ID:{supplier_id}")
        lookup.setdefault(client_id, []).append(f"→ {target_name} [{label}]")

        # Incoming to supplier
        source_name = id_to_name.get(client_id, f"ID:{client_id}")
        lookup.setdefault(supplier_id, []).append(f"← {source_name} [{label}]")

    return lookup


def _build_element_chunk(
    row: pd.Series,
    pkg_paths: dict[int, str],
    tv_lookup: dict[int, list[str]],
    con_lookup: dict[int, list[str]],
) -> dict:
    oid      = row["Object_ID"]
    stereo   = row.get("Stereotype") or ""
    pkg_path = pkg_paths.get(row["Package_ID"], "?")
    notes    = (row.get("Notes") or "").strip()
    tags     = tv_lookup.get(oid, [])
    cons     = con_lookup.get(oid, [])

    # Enriched description — TaggedValues + Connectors included
    description_parts = []
    if notes:
        description_parts.append(notes)
    if tags:
        description_parts.append(f"Tags: {' | '.join(tags)}")
    if cons:
        description_parts.append(f"Verbindungen: {' | '.join(cons)}")

    return {
        # Fields for EAIndexer.index_elements()
        "real_name":   row["Name"],
        "kind":        "element",
        "ea_type":     row["Object_Type"],
        "stereotype":  stereo,
        "parent_path": pkg_path,
        "description": " | ".join(description_parts),
        # Extra fields für Metadata
        "guid":        row["GUID"],
        "object_id":   int(oid),
    }