"""Bootstrap CLI: populate a Zotero group library from Notion pages.

For each relevant Notion page, fetches the item from the user's personal
Zotero library and creates it in the target group library if it isn't
already there (detected via owl:sameAs relations). Also creates sync_state
entries so webhook events have a baseline for three-way merge.
"""

import asyncio
import logging
import os
import re
import sys

from notero_sync.config import Settings
from notero_sync.db.repository import Repository
from notero_sync.notion.client import NotionClient
from notero_sync.notion.property_parser import extract_syncable_properties
from notero_sync.sync.collection_resolver import CollectionResolver
from notero_sync.sync.field_map import FIELD_MAP_BY_NOTION
from notero_sync.utils.zotero_uri import parse_zotero_uri
from notero_sync.zotero.client import ZoteroClient, ZoteroNotFoundError

logger = logging.getLogger(__name__)

# Fields that are library-specific and must be stripped when copying to another library
_STRIP_FIELDS = {"key", "version", "collections", "relations", "dateAdded", "dateModified"}


def _copy_item_data(source_data: dict) -> dict:
    """Build a clean item payload suitable for creation in another library."""
    return {k: v for k, v in source_data.items() if k not in _STRIP_FIELDS}


def _find_group_item_key(relations: dict, group_id: int) -> str | None:
    """Extract the item key from an owl:sameAs relation pointing to the group."""
    same_as = relations.get("owl:sameAs", [])
    if isinstance(same_as, str):
        same_as = [same_as]
    pattern = re.compile(rf"groups/{group_id}/items/([A-Z0-9]+)")
    for uri in same_as:
        m = pattern.search(uri)
        if m:
            return m.group(1)
    return None


async def _sync_attachment(
    zotero_client: ZoteroClient,
    group_id: int,
    group_item_key: str,
    filepath: str,
) -> bool:
    """Upload a local PDF as an imported_file attachment on a group item.

    Returns True if an attachment was created, False if skipped.
    """
    if not os.path.isfile(filepath):
        logger.warning("File not found: %s", filepath)
        return False

    # Check if group item already has a PDF attachment
    try:
        group_children = await zotero_client.get_children(
            "groups", group_id, group_item_key, item_type="attachment",
        )
        for child in group_children:
            if child.data.get("contentType") == "application/pdf":
                logger.debug("Group item %s already has a PDF attachment", group_item_key)
                return False
    except Exception:
        pass

    await zotero_client.upload_attachment("groups", group_id, group_item_key, filepath)
    return True


async def bootstrap() -> None:
    settings = Settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not settings.zotero_group_id:
        logger.error("ZOTERO_GROUP_ID must be set to bootstrap a group library")
        sys.exit(1)

    group_id = settings.zotero_group_id

    repo = Repository(settings.database_url)
    await repo.init_db()

    notion_client = NotionClient(settings.notion_api_key)
    zotero_client = ZoteroClient(settings.zotero_api_key)
    collection_resolver = CollectionResolver(repo, zotero_client)

    try:
        logger.info("Querying all pages from Notion database %s", settings.notion_database_id)
        pages = await notion_client.query_all_pages(settings.notion_database_id)
        logger.info("Found %d pages", len(pages))

        created = 0
        already_in_group = 0
        attachments_created = 0
        skipped = 0

        for page in pages:
            page_id = page["id"]
            properties = page.get("properties", {})
            parsed = extract_syncable_properties(properties)

            relevant = parsed.get("Relevant?")
            if relevant not in ("Yes", "Highly"):
                logger.debug("Page %s has Relevant=%s, skipping", page_id, relevant)
                skipped += 1
                continue

            zotero_uri = parsed.get("zotero_uri")
            if not zotero_uri:
                logger.debug("Page %s has no Zotero URI, skipping", page_id)
                skipped += 1
                continue

            ref = parse_zotero_uri(zotero_uri)
            if not ref:
                logger.warning("Cannot parse Zotero URI '%s' on page %s", zotero_uri, page_id)
                skipped += 1
                continue

            # Check if already bootstrapped
            existing = await repo.get_sync_state(page_id)
            if existing:
                logger.debug("Page %s already has sync state, skipping", page_id)
                skipped += 1
                continue

            # Fetch item from personal library
            try:
                source_item = await zotero_client.get_item(
                    ref.library_type, ref.library_id, ref.item_key
                )
            except ZoteroNotFoundError:
                logger.warning("Zotero item %s not found, skipping page %s", ref.item_key, page_id)
                skipped += 1
                continue

            # Check if item already exists in the group via owl:sameAs
            group_item_key = _find_group_item_key(
                source_item.data.get("relations", {}), group_id
            )

            if group_item_key:
                # Item already in group — just fetch version for sync state
                try:
                    group_item = await zotero_client.get_item(
                        "groups", group_id, group_item_key
                    )
                except ZoteroNotFoundError:
                    # Stale relation — treat as missing
                    group_item_key = None

            if not group_item_key:
                # Create item in group library
                new_data = _copy_item_data(source_item.data)
                group_item = await zotero_client.create_item(
                    "groups", group_id, new_data
                )
                group_item_key = group_item.key
                logger.info(
                    "Created item %s in group %d from %s (page %s)",
                    group_item_key, group_id, ref.item_key, page_id,
                )
                created += 1
            else:
                already_in_group += 1

            # Upload local PDF to group item if available
            filepath = parsed.get("File Path")
            if filepath:
                uploaded = await _sync_attachment(
                    zotero_client, group_id, group_item_key, filepath,
                )
                if uploaded:
                    logger.info("Uploaded PDF to group item %s: %s", group_item_key, os.path.basename(filepath))
                    attachments_created += 1

            # Build snapshot from current Notion values
            snapshot = {}
            for notion_name in FIELD_MAP_BY_NOTION:
                if notion_name in parsed:
                    snapshot[notion_name] = parsed[notion_name]

            await repo.upsert_sync_state(
                notion_page_id=page_id,
                zotero_item_key=group_item_key,
                zotero_group_id=group_id,
                last_zotero_version=group_item.version,
                property_snapshot=snapshot,
            )
            logger.info("Synced page %s → group item %s", page_id, group_item_key)

        # Refresh collection cache for the group
        await collection_resolver.ensure_cache("groups", group_id)
        logger.info("Cached collections for groups/%d", group_id)

        logger.info(
            "Bootstrap complete: %d items created, %d already in group, "
            "%d PDF attachments linked, %d skipped",
            created, already_in_group, attachments_created, skipped,
        )

    finally:
        await notion_client.close()
        await zotero_client.close()
        await repo.close()


def main():
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()
