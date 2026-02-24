"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from notero_sync.config import Settings
from notero_sync.db.repository import Repository
from notero_sync.notion.client import NotionClient
from notero_sync.sync.collection_resolver import CollectionResolver
from notero_sync.sync.engine import SyncEngine
from notero_sync.sync.note_sync import NoteSyncEngine
from notero_sync.webhook import handler as webhook_handler
from notero_sync.webhook.handler import router as webhook_router
from notero_sync.zotero.client import ZoteroClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Initialize clients
    repo = Repository(settings.database_url)
    await repo.init_db()

    notion_client = NotionClient(settings.notion_api_key)
    zotero_client = ZoteroClient(settings.zotero_api_key)
    collection_resolver = CollectionResolver(repo, zotero_client)

    sync_engine = SyncEngine(repo, notion_client, zotero_client, collection_resolver)
    note_sync_engine = NoteSyncEngine(
        repo, notion_client, zotero_client,
        delete_orphaned=settings.delete_orphaned_notes,
    )

    # Inject dependencies into webhook handler
    webhook_handler.configure(
        settings, repo, sync_engine, note_sync_engine, notion_client
    )

    logger.info("Notero reverse sync server started")
    yield

    # Cleanup
    await notion_client.close()
    await zotero_client.close()
    await repo.close()
    logger.info("Notero reverse sync server stopped")


app = FastAPI(title="Notero Reverse Sync", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    settings = Settings()
    uvicorn.run(
        "notero_sync.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
