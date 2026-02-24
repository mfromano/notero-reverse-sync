"""Core sync engine: diff → merge → patch pipeline for properties."""

import logging

from notero_sync.db.repository import Repository
from notero_sync.notion.client import NotionClient
from notero_sync.notion.property_parser import extract_syncable_properties
from notero_sync.sync.collection_resolver import CollectionResolver
from notero_sync.sync.field_map import (
    FIELD_MAP_BY_NOTION,
    NOTERO_TAG,
    MergeStrategy,
    notion_tags_to_zotero,
    zotero_tags_to_list,
)
from notero_sync.sync.tag_merger import three_way_merge
from notero_sync.utils.zotero_uri import ZoteroItemRef, parse_zotero_uri
from notero_sync.zotero.client import ZoteroClient, ZoteroConflictError, ZoteroNotFoundError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1


class SyncEngine:
    def __init__(
        self,
        repo: Repository,
        notion_client: NotionClient,
        zotero_client: ZoteroClient,
        collection_resolver: CollectionResolver,
    ) -> None:
        self._repo = repo
        self._notion = notion_client
        self._zotero = zotero_client
        self._collections = collection_resolver

    async def sync_page_properties(self, notion_page_id: str) -> None:
        """Sync property changes from a Notion page to the corresponding Zotero item."""
        # 1. Fetch page properties from Notion
        properties = await self._notion.get_page_properties(notion_page_id)
        parsed = extract_syncable_properties(properties)

        # 2. Check relevance filter
        relevant = parsed.get("Relevant?")
        if relevant not in ("Yes", "Highly"):
            logger.debug("Page %s has Relevant=%s, skipping sync", notion_page_id, relevant)
            return

        # 3. Extract Zotero URI
        zotero_uri = parsed.get("zotero_uri")
        if not zotero_uri:
            logger.warning("Page %s has no Zotero URI, skipping", notion_page_id)
            return

        ref = parse_zotero_uri(zotero_uri)
        if not ref:
            logger.warning("Cannot parse Zotero URI '%s' on page %s", zotero_uri, notion_page_id)
            return

        # 3. Load previous snapshot
        sync_state = await self._repo.get_sync_state(notion_page_id)
        if sync_state and sync_state.deleted:
            logger.info("Page %s is marked deleted, skipping", notion_page_id)
            return

        base_snapshot = sync_state.property_snapshot if sync_state else {}

        # 4. Fetch current Zotero item and attempt merge+patch with retry
        import asyncio

        for attempt in range(MAX_RETRIES):
            try:
                await self._do_merge_and_patch(
                    notion_page_id, ref, parsed, base_snapshot
                )
                return
            except ZoteroConflictError:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_SECONDS * (attempt + 1)
                    logger.warning(
                        "Version conflict on %s, retrying in %ds (attempt %d/%d)",
                        ref.item_key, wait, attempt + 1, MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "Version conflict on %s after %d retries, giving up",
                        ref.item_key, MAX_RETRIES,
                    )
            except ZoteroNotFoundError:
                logger.warning("Zotero item %s not found (404), marking deleted", ref.item_key)
                await self._repo.mark_deleted(notion_page_id)
                return

    async def _do_merge_and_patch(
        self,
        notion_page_id: str,
        ref: ZoteroItemRef,
        notion_props: dict,
        base_snapshot: dict,
    ) -> None:
        """Fetch Zotero item, compute diff, merge, and PATCH."""
        zotero_item = await self._zotero.get_item(
            ref.library_type, ref.library_id, ref.item_key
        )
        zotero_data = zotero_item.data
        patch_data: dict = {}

        for notion_name, field_mapping in FIELD_MAP_BY_NOTION.items():
            notion_value = notion_props.get(notion_name)
            if notion_value is None and notion_name not in notion_props:
                continue

            if field_mapping.merge_strategy == MergeStrategy.THREE_WAY:
                merged = await self._merge_array_field(
                    field_mapping, notion_value, zotero_data, base_snapshot, ref
                )
                if merged is not None:
                    if field_mapping.zotero_field == "tags":
                        patch_data["tags"] = notion_tags_to_zotero(merged)
                    elif field_mapping.zotero_field == "collections":
                        patch_data["collections"] = merged

            elif field_mapping.merge_strategy == MergeStrategy.SCALAR:
                new_value = self._merge_scalar_field(
                    field_mapping, notion_value, zotero_data, base_snapshot
                )
                if new_value is not None:
                    patch_data[field_mapping.zotero_field] = new_value

        version_to_store = zotero_item.version
        if not patch_data:
            logger.debug("No changes to sync for page %s", notion_page_id)
        else:
            logger.info(
                "Patching Zotero item %s with fields: %s",
                ref.item_key, list(patch_data.keys()),
            )
            version_to_store = await self._zotero.patch_item(
                ref.library_type, ref.library_id, ref.item_key,
                patch_data, zotero_item.version,
            )

        # Build new snapshot from current Notion values
        new_snapshot = self._build_snapshot(notion_props)
        await self._repo.upsert_sync_state(
            notion_page_id=notion_page_id,
            zotero_item_key=ref.item_key,
            zotero_group_id=ref.library_id,
            last_zotero_version=version_to_store,
            property_snapshot=new_snapshot,
        )

    async def _merge_array_field(
        self,
        field_mapping,
        notion_value: list[str] | None,
        zotero_data: dict,
        base_snapshot: dict,
        ref: ZoteroItemRef,
    ) -> list[str] | None:
        """Three-way merge for tags or collections."""
        notion_current = notion_value or []
        base = base_snapshot.get(field_mapping.notion_name, [])

        if field_mapping.zotero_field == "tags":
            zotero_current = zotero_tags_to_list(zotero_data.get("tags", []))
            preserve = {NOTERO_TAG}
            merged = three_way_merge(base, notion_current, zotero_current, preserve=preserve)
            if set(merged) != set(zotero_current):
                return merged
            return None

        elif field_mapping.zotero_field == "collections":
            zotero_current_keys = zotero_data.get("collections", [])
            # Convert Notion names to keys
            notion_keys = await self._collections.names_to_keys(
                ref.library_type, ref.library_id, notion_current
            )
            # Convert base names to keys
            base_keys = await self._collections.names_to_keys(
                ref.library_type, ref.library_id, base
            )
            merged = three_way_merge(base_keys, notion_keys, zotero_current_keys)
            if set(merged) != set(zotero_current_keys):
                return merged
            return None

        return None

    def _merge_scalar_field(
        self,
        field_mapping,
        notion_value: str | None,
        zotero_data: dict,
        base_snapshot: dict,
    ) -> str | None:
        """Resolve scalar field: Notion wins unless both changed (then Zotero wins)."""
        notion_current = notion_value or ""
        base = base_snapshot.get(field_mapping.notion_name, "")
        zotero_current = zotero_data.get(field_mapping.zotero_field, "")

        notion_changed = notion_current != base
        zotero_changed = zotero_current != base

        if not notion_changed:
            return None  # Notion didn't change, no action

        if notion_changed and not zotero_changed:
            return notion_current

        # Both changed — Zotero wins (conservative)
        logger.warning(
            "Conflict on field '%s': both Notion and Zotero changed. Zotero wins.",
            field_mapping.zotero_field,
        )
        return None

    def _build_snapshot(self, notion_props: dict) -> dict:
        """Build a property snapshot from current Notion values."""
        snapshot = {}
        for notion_name in FIELD_MAP_BY_NOTION:
            if notion_name in notion_props:
                snapshot[notion_name] = notion_props[notion_name]
        return snapshot
