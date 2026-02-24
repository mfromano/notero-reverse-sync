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

# Matches personal library URIs like https://zotero.org/mfromano/items/WFHVZPHT
_ZOTERO_USER_SLUG_RE = re.compile(
    r"https?://(?:www\.)?zotero\.org/([a-zA-Z][a-zA-Z0-9_-]*)/items/([A-Z0-9]+)"
)


def parse_zotero_uri(uri: str) -> ZoteroItemRef | None:
    """Parse a Zotero URI into its components.

    Accepts URIs like:
        https://www.zotero.org/groups/483726/items/A5X7AKTH
        https://zotero.org/users/12345/items/ABCD1234
        https://zotero.org/mfromano/items/WFHVZPHT  (personal library by username)
    """
    m = _ZOTERO_URI_RE.search(uri)
    if m:
        return ZoteroItemRef(
            library_type=m.group(1),
            library_id=int(m.group(2)),
            item_key=m.group(3),
        )

    # Fall back to username-slug URIs — use user ID 0 (Zotero API alias for
    # "the owner of the current API key").
    m = _ZOTERO_USER_SLUG_RE.search(uri)
    if m:
        return ZoteroItemRef(
            library_type="users",
            library_id=0,
            item_key=m.group(2),
        )

    return None
