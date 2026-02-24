"""Resolve collection names to keys and vice versa."""

import logging
import time

from notero_sync.db.repository import Repository
from notero_sync.zotero.client import ZoteroClient

logger = logging.getLogger(__name__)

# Refresh collection cache every 10 minutes
CACHE_TTL_SECONDS = 600


class CollectionResolver:
    def __init__(self, repo: Repository, zotero_client: ZoteroClient) -> None:
        self._repo = repo
        self._zotero = zotero_client
        self._last_refresh: dict[int, float] = {}  # group_id -> timestamp

    async def ensure_cache(self, library_type: str, group_id: int) -> None:
        """Refresh the collection cache if stale."""
        last = self._last_refresh.get(group_id, 0)
        if time.time() - last < CACHE_TTL_SECONDS:
            return

        logger.info("Refreshing collection cache for group %d", group_id)
        collections = await self._zotero.get_collections(library_type, group_id)
        await self._repo.refresh_collections(group_id, collections)
        self._last_refresh[group_id] = time.time()

    async def names_to_keys(
        self, library_type: str, group_id: int, names: list[str]
    ) -> list[str]:
        """Convert collection names to keys. Unknown names are logged and skipped."""
        await self.ensure_cache(library_type, group_id)
        keys = []
        for name in names:
            key = await self._repo.get_collection_key(group_id, name)
            if key:
                keys.append(key)
            else:
                logger.warning(
                    "Collection name '%s' not found in group %d, skipping", name, group_id
                )
        return keys

    async def keys_to_names(
        self, library_type: str, group_id: int, keys: list[str]
    ) -> list[str]:
        """Convert collection keys to names."""
        await self.ensure_cache(library_type, group_id)
        names = []
        for key in keys:
            name = await self._repo.get_collection_name(group_id, key)
            if name:
                names.append(name)
            else:
                logger.warning(
                    "Collection key '%s' not found in group %d", key, group_id
                )
        return names
