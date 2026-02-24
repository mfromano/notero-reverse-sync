# Notero Reverse Sync

Reverse sync service for [Notero](https://github.com/dvanoni/notero) — propagates edits made in Notion back to Zotero group libraries.

Notero syncs bibliographic items **one-way** from Zotero to Notion. This standalone service closes the loop by listening for Notion webhook events and writing changes back via the Zotero Web API.

## What syncs back

**Properties** (from `page.properties_updated` webhooks):

| Field | Strategy |
|-------|----------|
| Tags | Three-way merge (preserves tags added in both Notion and Zotero) |
| Collections | Three-way merge (resolves names to Zotero collection keys) |
| Abstract | Notion wins, unless both sides changed (then Zotero wins) |
| Short Title | Same as Abstract |
| Extra | Same as Abstract |

Title, Authors, Date, DOI, and other bibliographic metadata are **not** synced back — Zotero remains authoritative for those fields.

**Notes** (from `page.content_updated` webhooks):

- Edited Zotero notes under the "Zotero Notes" heading are synced back as HTML
- New blocks added under that heading create new child note items in Zotero

## How it works

```
Notion DB (edited by user)
       |
       | Webhook (~1 min aggregation)
       v
  FastAPI Server ── verifies HMAC signature, deduplicates, enqueues background task
       |
       v
  Sync Engine ── fetches Notion page + Zotero item
       |           loads snapshot from SQLite (common ancestor)
       |           computes three-way merge (arrays) or last-write-wins (scalars)
       |           PATCHes Zotero with If-Unmodified-Since-Version
       v
  SQLite ── stores sync state, property snapshots, note content hashes
```

Version conflicts (412) are retried up to 3 times with linear backoff. Deleted Zotero items (404) are marked and skipped.

## Setup

### Prerequisites

- Python 3.11+
- A [Notion internal integration](https://www.notion.so/my-integrations) with webhook capability
- A [Zotero API key](https://www.zotero.org/settings/keys) with write access to your group library
- [ngrok](https://ngrok.com/) (for local development)

### Installation

```bash
git clone <repo-url> && cd notero-zotero-sync
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configuration

```bash
cp .env.example .env
```

Fill in your `.env`:

| Variable | Description |
|----------|-------------|
| `NOTION_API_KEY` | Notion integration token |
| `NOTION_DATABASE_ID` | ID of the Notero-managed Notion database |
| `NOTION_WEBHOOK_SECRET` | Secret for verifying webhook signatures |
| `ZOTERO_API_KEY` | Zotero API key with group write access |
| `DATABASE_URL` | SQLite URL (default: `sqlite+aiosqlite:///./notero_sync.db`) |
| `DELETE_ORPHANED_NOTES` | Delete Zotero notes when removed from Notion (default: `false`) |

### Bootstrap

Before processing webhooks, establish a baseline snapshot so the three-way merge has a common ancestor:

```bash
notero-bootstrap
```

This reads all pages from your Notion database and records their current property values + Zotero item versions in SQLite. It does **not** write anything to Zotero.

### Run the server

```bash
uvicorn notero_sync.main:app --reload
```

### Expose with ngrok

```bash
ngrok http 8000
```

Register the ngrok URL (`https://<id>.ngrok-free.app/webhook/notion`) as the webhook target in your Notion integration settings.

> **Note:** When the ngrok tunnel restarts, the URL changes and you must re-register the webhook.

## Testing

```bash
pytest -v
```

The test suite covers:
- Zotero URI parsing
- Three-way tag/collection merging
- Notion block to HTML conversion
- Note section extraction
- Scalar field conflict resolution

## Project structure

```
src/notero_sync/
  main.py                  # FastAPI app + lifespan
  config.py                # Pydantic Settings
  bootstrap.py             # CLI: initial snapshot of all pages
  webhook/
    handler.py             # POST /webhook/notion
    models.py              # Webhook payload models
  notion/
    client.py              # Async Notion API client
    property_parser.py     # Notion properties -> Python values
    block_parser.py        # Notion blocks -> Zotero HTML
  zotero/
    client.py              # Async Zotero API client
  sync/
    engine.py              # Property sync pipeline
    note_sync.py           # Note/annotation reverse sync
    field_map.py           # Field definitions + merge strategies
    tag_merger.py          # Three-way merge algorithm
    collection_resolver.py # Collection name <-> key mapping
  db/
    models.py              # SQLAlchemy models
    repository.py          # CRUD operations
  utils/
    zotero_uri.py          # Parse Zotero URIs
```
