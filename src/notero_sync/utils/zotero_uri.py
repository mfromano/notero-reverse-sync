import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ZoteroItemRef:
    """Parsed reference to a Zotero item."""

    library_type: str  # "groups" or "users"
    library_id: int
    item_key: str

    @property
    def api_base(self) -> str:
        return f"https://api.zotero.org/{self.library_type}/{self.library_id}"

    @property
    def item_url(self) -> str:
        return f"{self.api_base}/items/{self.item_key}"


_ZOTERO_URI_RE = re.compile(
    r"https?://(?:www\.)?zotero\.org/(users|groups)/(\d+)/items/([A-Z0-9]+)"
)


def parse_zotero_uri(uri: str) -> ZoteroItemRef | None:
    """Parse a Zotero URI into its components.

    Accepts URIs like:
        https://www.zotero.org/groups/483726/items/A5X7AKTH
        https://zotero.org/users/12345/items/ABCD1234
    """
    m = _ZOTERO_URI_RE.search(uri)
    if not m:
        return None
    return ZoteroItemRef(
        library_type=m.group(1),
        library_id=int(m.group(2)),
        item_key=m.group(3),
    )
