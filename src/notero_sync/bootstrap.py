"""Bootstrap CLI: snapshot all existing Notion pages without writing to Zotero.

Creates initial sync_state entries so the first webhook events have a baseline
for three-way merge instead of treating everything as new.
"""

import asyncio
import logging
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


async def bootstrap() -> None:
    settings = Settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

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

            # Fetch current Zotero version (read-only, no writes)
            try:
                zotero_item = await zotero_client.get_item(
                    ref.library_type, ref.library_id, ref.item_key
                )
            except ZoteroNotFoundError:
                logger.warning("Zotero item %s not found, skipping page %s", ref.item_key, page_id)
                skipped += 1
                continue

            # Build snapshot from current Notion values
            snapshot = {}
            for notion_name in FIELD_MAP_BY_NOTION:
                if notion_name in parsed:
                    snapshot[notion_name] = parsed[notion_name]

            await repo.upsert_sync_state(
                notion_page_id=page_id,
                zotero_item_key=ref.item_key,
                zotero_group_id=ref.library_id,
                last_zotero_version=zotero_item.version,
                property_snapshot=snapshot,
            )
            created += 1
            logger.info("Bootstrapped page %s → %s", page_id, ref.item_key)

        # Also refresh collection cache for all encountered groups
        groups_seen = set()
        for page in pages:
            props = page.get("properties", {})
            parsed = extract_syncable_properties(props)
            uri = parsed.get("zotero_uri")
            if uri:
                ref = parse_zotero_uri(uri)
                if ref:
                    groups_seen.add((ref.library_type, ref.library_id))

        for lib_type, lib_id in groups_seen:
            await collection_resolver.ensure_cache(lib_type, lib_id)
            logger.info("Cached collections for %s/%d", lib_type, lib_id)

        logger.info("Bootstrap complete: %d created, %d skipped", created, skipped)

    finally:
        await notion_client.close()
        await zotero_client.close()
        await repo.close()


def main():
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()
