"""Three-way merge for array fields (tags, collections)."""

import logging

logger = logging.getLogger(__name__)


def three_way_merge(
    base: list[str],
    notion_current: list[str],
    zotero_current: list[str],
    *,
    preserve: set[str] | None = None,
) -> list[str]:
    """Compute a three-way merge for an array field.

    Args:
        base: Snapshot from last sync (common ancestor).
        notion_current: Current values in Notion.
        zotero_current: Current values in Zotero.
        preserve: Values that must always be in the result.

    Returns:
        Merged list of values.

    Example:
        base = [A, B, C]
        notion = [A, C, D]      # added D, removed B
        zotero = [A, B, C, E]   # added E

        Result: [A, C, D, E]    # apply Notion's changes to Zotero's state
    """
    base_set = set(base)
    notion_set = set(notion_current)
    zotero_set = set(zotero_current)

    # What Notion did since base
    notion_added = notion_set - base_set
    notion_removed = base_set - notion_set

    # Start from Zotero's current state and apply Notion's changes
    result = zotero_set.copy()
    result |= notion_added
    result -= notion_removed

    # Always preserve certain values
    if preserve:
        result |= preserve

    # Maintain a stable order: Zotero's order first, then new additions sorted
    ordered = [v for v in zotero_current if v in result]
    new_items = sorted(result - set(ordered))
    ordered.extend(new_items)

    return ordered
