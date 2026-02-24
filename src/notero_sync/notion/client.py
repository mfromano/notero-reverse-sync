import logging

import httpx

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2022-06-28"


class NotionClient:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=NOTION_API_BASE,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_page(self, page_id: str) -> dict:
        resp = await self._client.get(f"/pages/{page_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_page_properties(self, page_id: str) -> dict:
        """Get a page and return its properties dict."""
        page = await self.get_page(page_id)
        return page.get("properties", {})

    async def get_block_children(
        self, block_id: str, *, recursive: bool = False
    ) -> list[dict]:
        """Get all child blocks of a block/page, handling pagination."""
        blocks = []
        cursor = None

        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            resp = await self._client.get(
                f"/blocks/{block_id}/children", params=params
            )
            resp.raise_for_status()
            data = resp.json()
            blocks.extend(data["results"])

            if not data.get("has_more"):
                break
            cursor = data["next_cursor"]

        if recursive:
            for block in list(blocks):
                if block.get("has_children"):
                    children = await self.get_block_children(
                        block["id"], recursive=True
                    )
                    block["children"] = children

        return blocks

    async def query_database(
        self, database_id: str, *, start_cursor: str | None = None, page_size: int = 100
    ) -> dict:
        """Query a Notion database, returning one page of results."""
        body: dict = {"page_size": page_size}
        if start_cursor:
            body["start_cursor"] = start_cursor
        resp = await self._client.post(f"/databases/{database_id}/query", json=body)
        resp.raise_for_status()
        return resp.json()

    async def query_all_pages(self, database_id: str) -> list[dict]:
        """Query all pages in a Notion database."""
        pages = []
        cursor = None
        while True:
            result = await self.query_database(
                database_id, start_cursor=cursor
            )
            pages.extend(result["results"])
            if not result.get("has_more"):
                break
            cursor = result["next_cursor"]
        return pages
