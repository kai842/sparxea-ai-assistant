import pandas as pd
from ea_connector.reader_db import build_package_path
from ea_connector.model_config import (
    EXCLUDED_ELEMENT_TYPES, NOTE_ELEMENT_TYPES,
    EMPTY_TAG_VALUES, MAX_CONNECTORS_PER_CHUNK, MAX_TAGS_PER_CHUNK
)


def build_chunks(data: dict[str, pd.DataFrame]) -> list[dict]:
    objects       = data["objects"]
    packages      = data["packages"]
    connectors    = data["connectors"]
    tagged_values = data["tagged_values"]
    diagrams      = data.get("diagrams", pd.DataFrame())
    diagram_objs  = data.get("diagram_objects", pd.DataFrame())

    pkg_paths     = build_package_path(packages)
    tv_lookup     = _build_tv_lookup(tagged_values)
    con_lookup    = _build_connector_lookup(connectors, objects)
    note_lookup   = _build_note_lookup(objects, connectors)
    diag_lookup   = _build_diagram_lookup(diagram_objs, diagrams)

    chunks = []
    for _, row in objects.iterrows():
        if row["Object_Type"] in EXCLUDED_ELEMENT_TYPES:
            continue
        if row["Object_Type"] in NOTE_ELEMENT_TYPES:
            continue  # Notes are embedded into their linked elements
        chunk = _build_element_chunk(
            row, pkg_paths, tv_lookup, con_lookup, note_lookup, diag_lookup
        )
        chunks.append(chunk)

    return chunks


def _build_tv_lookup(tagged_values: pd.DataFrame) -> dict[int, list[str]]:
    lookup = {}
    for _, row in tagged_values.iterrows():
        if row["Value"] in EMPTY_TAG_VALUES:
            continue
        lookup.setdefault(row["Object_ID"], []).append(
            f"{row['Name']}={row['Value']}"
        )
    return lookup


def _build_connector_lookup(
    connectors: pd.DataFrame, objects: pd.DataFrame
) -> dict[int, list[str]]:
    id_to_name = dict(zip(objects["Object_ID"], objects["Name"]))
    lookup = {}

    for _, con in connectors.iterrows():
        client_id   = con["ClientID"]
        supplier_id = con["SupplierID"]
        con_type    = con["Type"] or ""
        con_name    = con["Name"] or ""
        label       = f"{con_name} ({con_type})" if con_name else con_type

        target_name = id_to_name.get(supplier_id, f"ID:{supplier_id}")
        lookup.setdefault(client_id, []).append(f"→ {target_name} [{label}]")

        source_name = id_to_name.get(client_id, f"ID:{client_id}")
        lookup.setdefault(supplier_id, []).append(f"← {source_name} [{label}]")

    return lookup


def _build_note_lookup(
    objects: pd.DataFrame, connectors: pd.DataFrame
) -> dict[int, list[str]]:
    """
    Resolves NoteLink connectors: maps each linked element's Object_ID
    to the text content of its connected Note elements.
    """
    note_ids = set(
        objects.loc[objects["Object_Type"].isin(NOTE_ELEMENT_TYPES), "Object_ID"]
    )
    id_to_notes = dict(
        zip(objects["Object_ID"], objects["Notes"].fillna(""))
    )
    lookup = {}

    for _, con in connectors.iterrows():
        if con["Type"] != "NoteLink":
            continue
        client_id   = con["ClientID"]
        supplier_id = con["SupplierID"]

        # One end is the Note, the other is the linked element
        if client_id in note_ids:
            note_text = id_to_notes.get(client_id, "").strip()
            if note_text:
                lookup.setdefault(supplier_id, []).append(note_text)
        elif supplier_id in note_ids:
            note_text = id_to_notes.get(supplier_id, "").strip()
            if note_text:
                lookup.setdefault(client_id, []).append(note_text)

    return lookup


def _build_diagram_lookup(
    diagram_objs: pd.DataFrame, diagrams: pd.DataFrame
) -> dict[int, list[str]]:
    if diagram_objs.empty or diagrams.empty:
        return {}

    id_to_diag_name = dict(zip(diagrams["Diagram_ID"], diagrams["Name"]))
    lookup = {}

    for _, row in diagram_objs.iterrows():
        diag_name = id_to_diag_name.get(row["Diagram_ID"]) 
        if diag_name:
            lookup.setdefault(row["Object_ID"], []).append(diag_name)

    return lookup


def _build_element_chunk(
    row: pd.Series,
    pkg_paths: dict[int, str],
    tv_lookup: dict[int, list[str]],
    con_lookup: dict[int, list[str]],
    note_lookup: dict[int, list[str]],
    diag_lookup: dict[int, list[str]],
) -> dict:
    oid      = row["Object_ID"]
    stereo   = row.get("Stereotype") or ""
    pkg_path = pkg_paths.get(row["Package_ID"], "?")
    notes    = (row.get("Notes") or "").strip()
    tags     = tv_lookup.get(oid, [])[:MAX_TAGS_PER_CHUNK]
    cons     = con_lookup.get(oid, [])[:MAX_CONNECTORS_PER_CHUNK]
    note_txts= note_lookup.get(oid, [])
    diagrams = diag_lookup.get(oid, [])

    description_parts = []
    if notes:
        description_parts.append(notes)
    if note_txts:
        description_parts.append(f"Notizen: {' | '.join(note_txts)}")
    if tags:
        description_parts.append(f"Tags: {' | '.join(tags)}")
    if cons:
        description_parts.append(f"Verbindungen: {' | '.join(cons)}")
    if diagrams:
        description_parts.append(f"Diagramme: {', '.join(diagrams)}")

    return {
        "guid":        row["GUID"],
        "object_id":   int(oid),
        "real_name":   row["Name"],
        "kind":        "element",
        "ea_type":     row["Object_Type"],
        "stereotype":  stereo,
        "parent_path": pkg_path,
        "description": " | ".join(description_parts),
    }
