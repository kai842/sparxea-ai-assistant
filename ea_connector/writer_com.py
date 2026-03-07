import re
import logging
import win32com.client
import pythoncom


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------
write_logger = logging.getLogger("ea.writes")
write_logger.setLevel(logging.INFO)

_handler = logging.FileHandler("ea_write_audit.log", encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
write_logger.addHandler(_handler)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_repo():
    """Returns the active EA Repository via COM. EA must be open."""
    try:
        pythoncom.CoInitialize()
        ea = win32com.client.GetActiveObject("EA.App")
        return ea.Repository
    except Exception as e:
        raise RuntimeError(
            "Cannot connect to Sparx EA. "
            "Make sure EA is open with a model loaded, "
            "and that EA is registered for COM (Help → Register EA for COM)."
        ) from e


def _find_package_by_name(repo, package_name: str):
    """
    Searches all packages recursively for one matching package_name.
    Partial + case-insensitive match. Returns first match or None.
    """
    for i in range(repo.Models.Count):
        result = _search_package(repo.Models.GetAt(i), package_name)
        if result:
            return result
    return None


def _search_package(package, name: str):
    if name.strip().lower() in package.Name.strip().lower():
        return package
    for i in range(package.Packages.Count):
        result = _search_package(package.Packages.GetAt(i), name)
        if result:
            return result
    return None


def _find_element_by_name(repo, element_name: str):
    """
    Searches t_object via SQL for an element matching element_name.
    Strategy 1: case-insensitive exact match (LIKE without wildcards)
    Strategy 2: partial match (LIKE with wildcards) as fallback
    Returns (Object_ID, Package_ID) or None.
    """
    # Sanitize: strip whitespace and escape single quotes
    safe_name = element_name.strip().replace("'", "''")

    # Strategy 1: Exact match (LIKE is case-insensitive in SQLite)
    sql = f"SELECT Object_ID, Package_ID FROM t_object WHERE Name LIKE '{safe_name}'"
    result = repo.SQLQuery(sql)
    ids     = re.findall(r"<Object_ID>(\d+)</Object_ID>", result)
    pkg_ids = re.findall(r"<Package_ID>(\d+)</Package_ID>", result)
    if ids and pkg_ids:
        return int(ids[0]), int(pkg_ids[0])

    # Strategy 2: Partial match fallback
    sql_partial = f"SELECT Object_ID, Package_ID FROM t_object WHERE Name LIKE '%{safe_name}%'"
    result_partial = repo.SQLQuery(sql_partial)
    ids     = re.findall(r"<Object_ID>(\d+)</Object_ID>", result_partial)
    pkg_ids = re.findall(r"<Package_ID>(\d+)</Package_ID>", result_partial)
    if ids and pkg_ids:
        return int(ids[0]), int(pkg_ids[0])

    return None


def _log_write(action: str, details: dict) -> None:
    write_logger.info(f"WRITE | {action} | {details}")


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def create_element(
    name: str,
    ea_type: str,
    package_name: str,
    stereotype: str = "",
    notes: str = "",
) -> str:
    """
    Creates a new element or package in the specified package.
    Handles EA's strict API distinction between Package folders
    (t_package) and regular elements (t_object).
    """
    repo    = _get_repo()
    package = _find_package_by_name(repo, package_name)

    if not package:
        return f"❌ Package '{package_name}' not found."

    is_package = (ea_type.strip().lower() == "package")

    try:
        if is_package:
            new_item = package.Packages.AddNew(name, "Package")
            if notes:
                new_item.Notes = notes
            new_item.Update()
            if stereotype:
                new_item.Element.Stereotype = stereotype
                new_item.Element.Update()
            package.Packages.Refresh()
        else:
            new_item = package.Elements.AddNew(name, ea_type)
            if stereotype:
                new_item.Stereotype = stereotype
            if notes:
                new_item.Notes = notes
            new_item.Update()
            package.Elements.Refresh()

        _log_write("CREATE_ELEMENT", {
            "name": name, "type": ea_type,
            "package": package_name, "stereotype": stereotype,
        })
        return f"✅ [{ea_type}] '{name}' created in package '{package_name}'."

    except Exception as e:
        return f"❌ Error creating {ea_type} '{name}': {e}"


def update_element_notes(element_name: str, new_notes: str) -> str:
    """Updates the description/notes of an existing element."""
    repo   = _get_repo()
    result = _find_element_by_name(repo, element_name)

    if not result:
        return f"❌ Element '{element_name}' not found."

    object_id, _ = result
    element      = repo.GetElementByID(object_id)
    old_notes    = element.Notes
    element.Notes = new_notes
    element.Update()

    _log_write("UPDATE_NOTES", {
        "name": element_name,
        "old":  (old_notes or "")[:80],
        "new":  new_notes[:80],
    })
    return f"✅ Description of '{element_name}' updated successfully."


def set_tagged_value(element_name: str, tag_name: str, tag_value: str) -> str:
    """Sets or updates a Tagged Value on an existing element."""
    repo   = _get_repo()
    result = _find_element_by_name(repo, element_name)

    if not result:
        return f"❌ Element '{element_name}' not found."

    object_id, _ = result
    element      = repo.GetElementByID(object_id)

    # Update existing tag if found
    for i in range(element.TaggedValues.Count):
        tv = element.TaggedValues.GetAt(i)
        if tv.Name.lower() == tag_name.lower():
            old_value = tv.Value
            tv.Value  = tag_value
            tv.Update()
            _log_write("UPDATE_TAG", {
                "element": element_name, "tag": tag_name,
                "old": old_value, "new": tag_value,
            })
            return f"✅ Tagged Value '{tag_name}' on '{element_name}' set to '{tag_value}'."

    # Create new tag
    tv = element.TaggedValues.AddNew(tag_name, tag_value)
    tv.Update()
    element.TaggedValues.Refresh()

    _log_write("CREATE_TAG", {
        "element": element_name, "tag": tag_name, "value": tag_value,
    })
    return f"✅ New Tagged Value '{tag_name}={tag_value}' created on '{element_name}'."


def create_connector(
    source_name: str,
    target_name: str,
    connector_type: str,
    stereotype: str = "",
    name: str = "",
) -> str:
    """Creates a connector between two existing elements."""
    repo = _get_repo()
    src  = _find_element_by_name(repo, source_name)
    tgt  = _find_element_by_name(repo, target_name)

    if not src:
        return f"❌ Source element '{source_name}' not found."
    if not tgt:
        return f"❌ Target element '{target_name}' not found."

    try:
        src_element = repo.GetElementByID(src[0])
        connector   = src_element.Connectors.AddNew(name, connector_type)
        connector.SupplierID = tgt[0]
        if stereotype:
            connector.Stereotype = stereotype
        connector.Update()
        src_element.Connectors.Refresh()

        _log_write("CREATE_CONNECTOR", {
            "source": source_name, "target": target_name,
            "type": connector_type, "stereotype": stereotype,
        })
        return (
            f"✅ Connector [{connector_type}] "
            f"'{source_name}' → '{target_name}' created successfully."
        )
    except Exception as e:
        return f"❌ Error creating connector: {e}"
