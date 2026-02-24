"""Parse Notion property values into plain Python types."""

import logging

logger = logging.getLogger(__name__)


def parse_property_value(prop: dict) -> str | list[str] | None:
    """Parse a single Notion property into a Python value.

    Returns:
        - str for text/url/rich_text/select fields
        - list[str] for multi_select fields
        - None if empty or unsupported type
    """
    prop_type = prop.get("type")

    if prop_type == "title":
        parts = prop.get("title", [])
        return "".join(t.get("plain_text", "") for t in parts) or None

    if prop_type == "rich_text":
        parts = prop.get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in parts) or None

    if prop_type == "url":
        return prop.get("url")

    if prop_type == "select":
        sel = prop.get("select")
        return sel["name"] if sel else None

    if prop_type == "multi_select":
        items = prop.get("multi_select", [])
        return [item["name"] for item in items]

    if prop_type == "number":
        return prop.get("number")

    if prop_type == "checkbox":
        return prop.get("checkbox")

    if prop_type == "date":
        date_obj = prop.get("date")
        if date_obj:
            return date_obj.get("start")
        return None

    logger.debug("Unsupported Notion property type: %s", prop_type)
    return None


def extract_syncable_properties(properties: dict, zotero_uri_field: str = "Zotero URI") -> dict:
    """Extract the properties we care about from a Notion page's properties.

    Returns a dict with normalized keys matching our field map.
    """
    result = {}

    for name, prop in properties.items():
        if name == zotero_uri_field:
            result["zotero_uri"] = parse_property_value(prop)
            continue

        # Normalize the property name to match our field mapping
        key = name.strip()
        value = parse_property_value(prop)
        if value is not None:
            result[key] = value

    return result
