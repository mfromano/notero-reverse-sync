"""Maps Notion property names to Zotero item fields and defines sync behavior."""

from dataclasses import dataclass
from enum import Enum


class MergeStrategy(Enum):
    THREE_WAY = "three_way"  # For array fields (tags, collections)
    SCALAR = "scalar"  # For text fields (notion wins unless both changed)
    NO_SYNC = "no_sync"  # Don't sync back


@dataclass(frozen=True)
class FieldMapping:
    """Mapping from a Notion property name to a Zotero field."""

    notion_name: str
    zotero_field: str
    merge_strategy: MergeStrategy


# Fields that sync from Notion → Zotero
SYNCABLE_FIELDS: list[FieldMapping] = [
    FieldMapping("Tags", "tags", MergeStrategy.THREE_WAY),
    FieldMapping("Collections", "collections", MergeStrategy.THREE_WAY),
    FieldMapping("Abstract", "abstractNote", MergeStrategy.SCALAR),
    FieldMapping("Short Title", "shortTitle", MergeStrategy.SCALAR),
    FieldMapping("Extra", "extra", MergeStrategy.SCALAR),
]

# Lookup by Notion property name
FIELD_MAP_BY_NOTION: dict[str, FieldMapping] = {f.notion_name: f for f in SYNCABLE_FIELDS}

# Zotero tag marker that Notero adds - always preserve
NOTERO_TAG = "notion"


def notion_tags_to_zotero(tags: list[str]) -> list[dict]:
    """Convert a list of tag strings to Zotero tag format."""
    return [{"tag": t} for t in tags]


def zotero_tags_to_list(tags: list[dict]) -> list[str]:
    """Convert Zotero tag dicts to a list of tag strings."""
    return [t["tag"] for t in tags]
