"""Note/annotation reverse sync: Notion blocks → Zotero note items."""

import logging

from notero_sync.db.repository import Repository
from notero_sync.notion.block_parser import blocks_to_html, compute_blocks_hash
from notero_sync.notion.client import NotionClient
from notero_sync.utils.zotero_uri import ZoteroItemRef
from notero_sync.zotero.client import ZoteroClient, ZoteroConflictError, ZoteroNotFoundError

logger = logging.getLogger(__name__)

ZOTERO_NOTES_HEADING = "Zotero Notes"


class NoteSyncEngine:
    def __init__(
        self,
        repo: Repository,
        notion_client: NotionClient,
        zotero_client: ZoteroClient,
        *,
        delete_orphaned: bool = False,
    ) -> None:
        self._repo = repo
        self._notion = notion_client
        self._zotero = zotero_client
        self._delete_orphaned = delete_orphaned

    async def sync_page_notes(self, notion_page_id: str, ref: ZoteroItemRef) -> None:
        """Sync note content changes from a Notion page back to Zotero."""
        # 1. Fetch all top-level blocks of the page
        blocks = await self._notion.get_block_children(notion_page_id)

        # 2. Find the "Zotero Notes" heading and collect blocks under it
        note_sections = self._extract_note_sections(blocks)
        if not note_sections:
            logger.debug("No 'Zotero Notes' heading found on page %s", notion_page_id)
            return

        # 3. Get existing note sync states for this parent
        existing_states = await self._repo.get_note_sync_states_for_parent(
            ref.item_key, ref.library_id
        )
        tracked_block_ids = {s.notion_block_id: s for s in existing_states}

        # 4. Process each note section
        for section in note_sections:
            block_id = section["block_id"]
            child_blocks = section["blocks"]

            if not child_blocks:
                continue

            content_hash = compute_blocks_hash(child_blocks)

            if block_id in tracked_block_ids:
                # Existing tracked note — check for changes
                state = tracked_block_ids.pop(block_id)
                if content_hash != state.content_hash:
                    await self._update_existing_note(
                        state.zotero_note_key, ref, child_blocks, block_id, content_hash
                    )
                else:
                    logger.debug("Note block %s unchanged, skipping", block_id)
            else:
                # New note block — create in Zotero
                await self._create_new_note(ref, child_blocks, block_id, content_hash)

        # 5. Handle orphaned notes (tracked blocks that no longer exist)
        for block_id, state in tracked_block_ids.items():
            if self._delete_orphaned:
                logger.info("Deleting orphaned Zotero note %s", state.zotero_note_key)
                try:
                    note_item = await self._zotero.get_item(
                        ref.library_type, ref.library_id, state.zotero_note_key
                    )
                    await self._zotero.delete_item(
                        ref.library_type, ref.library_id,
                        state.zotero_note_key, note_item.version,
                    )
                except ZoteroNotFoundError:
                    pass
                await self._repo.delete_note_sync_state(block_id)
            else:
                logger.info(
                    "Orphaned note block %s (Zotero key %s) — skipping deletion",
                    block_id, state.zotero_note_key,
                )

    def _extract_note_sections(self, blocks: list[dict]) -> list[dict]:
        """Find the 'Zotero Notes' heading and extract note sections under it.

        Each direct child block under the heading is treated as a separate note.
        If the child block has children, those are the note content.
        Otherwise, we group consecutive non-heading blocks as a single note.
        """
        sections = []
        in_notes_section = False

        for block in blocks:
            bt = block.get("type", "")

            # Detect the "Zotero Notes" heading
            if bt in ("heading_1", "heading_2", "heading_3"):
                text = self._get_block_text(block)
                if text.strip() == ZOTERO_NOTES_HEADING:
                    in_notes_section = True
                    continue
                elif in_notes_section:
                    # Another heading ends the notes section
                    break

            if in_notes_section:
                # Each block under the heading is treated as a note section
                # If it has children, fetch them; otherwise the block itself is the note
                if block.get("has_children"):
                    sections.append({
                        "block_id": block["id"],
                        "blocks": block.get("children", [block]),
                    })
                else:
                    sections.append({
                        "block_id": block["id"],
                        "blocks": [block],
                    })

        return sections

    def _get_block_text(self, block: dict) -> str:
        bt = block.get("type", "")
        block_data = block.get(bt, {})
        rich_text = block_data.get("rich_text", [])
        return "".join(rt.get("plain_text", "") for rt in rich_text)

    async def _update_existing_note(
        self,
        zotero_note_key: str,
        ref: ZoteroItemRef,
        blocks: list[dict],
        block_id: str,
        content_hash: str,
    ) -> None:
        """Update an existing Zotero note with new content from Notion."""
        html = blocks_to_html(blocks)
        logger.info("Updating Zotero note %s from Notion block %s", zotero_note_key, block_id)

        try:
            note_item = await self._zotero.get_item(
                ref.library_type, ref.library_id, zotero_note_key
            )
            await self._zotero.patch_item(
                ref.library_type, ref.library_id, zotero_note_key,
                {"note": html}, note_item.version,
            )
            await self._repo.upsert_note_sync_state(
                notion_block_id=block_id,
                zotero_note_key=zotero_note_key,
                zotero_parent_key=ref.item_key,
                zotero_group_id=ref.library_id,
                content_hash=content_hash,
            )
        except ZoteroNotFoundError:
            logger.warning("Zotero note %s not found, removing tracking", zotero_note_key)
            await self._repo.delete_note_sync_state(block_id)
        except ZoteroConflictError:
            logger.warning("Version conflict updating note %s, will retry next cycle", zotero_note_key)

    async def _create_new_note(
        self,
        ref: ZoteroItemRef,
        blocks: list[dict],
        block_id: str,
        content_hash: str,
    ) -> None:
        """Create a new Zotero child note from a Notion block."""
        html = blocks_to_html(blocks)
        logger.info("Creating new Zotero note from Notion block %s", block_id)

        try:
            note_item = await self._zotero.create_note(
                ref.library_type, ref.library_id, ref.item_key, html
            )
            await self._repo.upsert_note_sync_state(
                notion_block_id=block_id,
                zotero_note_key=note_item.key,
                zotero_parent_key=ref.item_key,
                zotero_group_id=ref.library_id,
                content_hash=content_hash,
            )
        except Exception:
            logger.exception("Failed to create Zotero note from block %s", block_id)
