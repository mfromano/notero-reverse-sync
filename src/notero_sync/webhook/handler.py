"""Webhook endpoint for receiving Notion events."""

import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from notero_sync.config import Settings
from notero_sync.db.repository import Repository
from notero_sync.notion.client import NotionClient
from notero_sync.notion.property_parser import extract_syncable_properties
from notero_sync.sync.collection_resolver import CollectionResolver
from notero_sync.sync.engine import SyncEngine
from notero_sync.sync.note_sync import NoteSyncEngine
from notero_sync.utils.zotero_uri import parse_zotero_uri
from notero_sync.webhook.models import WebhookPayload
from notero_sync.zotero.client import ZoteroClient

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected at app startup
_settings: Settings | None = None
_repo: Repository | None = None
_sync_engine: SyncEngine | None = None
_note_sync_engine: NoteSyncEngine | None = None
_notion_client: NotionClient | None = None


def configure(
    settings: Settings,
    repo: Repository,
    sync_engine: SyncEngine,
    note_sync_engine: NoteSyncEngine,
    notion_client: NotionClient,
) -> None:
    global _settings, _repo, _sync_engine, _note_sync_engine, _notion_client
    _settings = settings
    _repo = repo
    _sync_engine = sync_engine
    _note_sync_engine = note_sync_engine
    _notion_client = notion_client


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Notion webhook HMAC-SHA256 signature."""
    expected = hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook/notion")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_notion_signature: str | None = Header(None),
):
    """Handle incoming Notion webhook events."""
    body = await request.body()

    # Verify signature
    if _settings and x_notion_signature:
        if not verify_signature(body, x_notion_signature, _settings.notion_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = WebhookPayload.model_validate_json(body)

    # Handle verification challenge
    if payload.verification_token:
        logger.info("Received webhook verification challenge")
        return {"challenge": payload.verification_token}

    # Process events
    if payload.events:
        for event in payload.events:
            page_id = event.data.get("page_id")
            if not page_id:
                logger.warning("Event %s has no page_id, skipping", event.id)
                continue

            # Dedup
            is_new = await _repo.record_event(event.id, page_id)
            if not is_new:
                logger.debug("Duplicate event %s, skipping", event.id)
                continue

            if event.type == "page.properties_updated":
                background_tasks.add_task(_process_property_update, event.id, page_id)
            elif event.type == "page.content_updated":
                background_tasks.add_task(_process_content_update, event.id, page_id)
            else:
                logger.debug("Ignoring event type: %s", event.type)

    return {"status": "ok"}


async def _process_property_update(event_id: str, page_id: str) -> None:
    """Background task: sync property changes to Zotero."""
    try:
        logger.info("Processing property update for page %s", page_id)
        await _sync_engine.sync_page_properties(page_id)
        await _repo.mark_event_processed(event_id)
    except Exception:
        logger.exception("Error processing property update for page %s", page_id)


async def _process_content_update(event_id: str, page_id: str) -> None:
    """Background task: sync note content changes to Zotero."""
    try:
        logger.info("Processing content update for page %s", page_id)

        # Get the Zotero URI from the page to know which item to update
        properties = await _notion_client.get_page_properties(page_id)
        parsed = extract_syncable_properties(properties)
        zotero_uri = parsed.get("zotero_uri")

        if not zotero_uri:
            logger.warning("Page %s has no Zotero URI, skipping note sync", page_id)
            return

        ref = parse_zotero_uri(zotero_uri)
        if not ref:
            logger.warning("Cannot parse Zotero URI on page %s", page_id)
            return

        await _note_sync_engine.sync_page_notes(page_id, ref)
        await _repo.mark_event_processed(event_id)
    except Exception:
        logger.exception("Error processing content update for page %s", page_id)
