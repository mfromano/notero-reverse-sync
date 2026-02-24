import asyncio
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

ZOTERO_API_BASE = "https://api.zotero.org"


class ZoteroConflictError(Exception):
    """Raised on 412 Precondition Failed (version conflict)."""

    def __init__(self, current_version: int):
        self.current_version = current_version
        super().__init__(f"Version conflict, current version: {current_version}")


class ZoteroNotFoundError(Exception):
    """Raised when a Zotero item is not found (404)."""


@dataclass
class ZoteroItem:
    key: str
    version: int
    data: dict


class ZoteroClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=ZOTERO_API_BASE,
            headers={
                "Zotero-API-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._cached_user_id: int | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def _get_user_id(self) -> int:
        """Resolve the numeric user ID for the current API key (cached)."""
        if self._cached_user_id is None:
            resp = await self._client.get(f"/keys/{self._api_key}")
            resp.raise_for_status()
            self._cached_user_id = resp.json()["userID"]
            logger.info("Resolved Zotero user ID: %d", self._cached_user_id)
        return self._cached_user_id

    async def _resolve_library_id(self, library_type: str, library_id: int) -> int:
        """Replace library_id=0 with the real user ID for user libraries."""
        if library_type == "users" and library_id == 0:
            return await self._get_user_id()
        return library_id

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make a request with rate-limit handling."""
        resp = await self._client.request(method, url, **kwargs)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "5"))
            logger.warning("Zotero rate limited, retrying after %d seconds", retry_after)
            await asyncio.sleep(retry_after)
            resp = await self._client.request(method, url, **kwargs)

        return resp

    async def get_item(self, library_type: str, library_id: int, item_key: str) -> ZoteroItem:
        library_id = await self._resolve_library_id(library_type, library_id)
        url = f"/{library_type}/{library_id}/items/{item_key}"
        resp = await self._request("GET", url)

        if resp.status_code == 404:
            raise ZoteroNotFoundError(f"Item not found: {url}")
        resp.raise_for_status()

        data = resp.json()
        version = int(resp.headers.get("Last-Modified-Version", data.get("version", 0)))
        return ZoteroItem(key=data["key"], version=version, data=data["data"])

    async def patch_item(
        self,
        library_type: str,
        library_id: int,
        item_key: str,
        data: dict,
        version: int,
    ) -> int:
        """PATCH a Zotero item. Returns the new version on success."""
        library_id = await self._resolve_library_id(library_type, library_id)
        url = f"/{library_type}/{library_id}/items/{item_key}"
        resp = await self._request(
            "PATCH",
            url,
            json=data,
            headers={"If-Unmodified-Since-Version": str(version)},
        )

        if resp.status_code == 412:
            new_version = int(resp.headers.get("Last-Modified-Version", "0"))
            raise ZoteroConflictError(new_version)
        if resp.status_code == 404:
            raise ZoteroNotFoundError(f"Item not found: {url}")
        resp.raise_for_status()

        return int(resp.headers.get("Last-Modified-Version", str(version)))

    async def create_note(
        self,
        library_type: str,
        library_id: int,
        parent_key: str,
        note_html: str,
        tags: list[dict] | None = None,
    ) -> ZoteroItem:
        """Create a child note on a Zotero item."""
        library_id = await self._resolve_library_id(library_type, library_id)
        url = f"/{library_type}/{library_id}/items"
        payload = [
            {
                "itemType": "note",
                "parentItem": parent_key,
                "note": note_html,
                "tags": tags or [],
            }
        ]
        resp = await self._request("POST", url, json=payload)
        resp.raise_for_status()

        result = resp.json()
        # Zotero returns {"successful": {"0": {...}}, ...}
        created = result["successful"]["0"]
        return ZoteroItem(
            key=created["key"],
            version=created["version"],
            data=created["data"],
        )

    async def get_child_notes(
        self, library_type: str, library_id: int, item_key: str
    ) -> list[ZoteroItem]:
        """Get all child note items for a parent item."""
        library_id = await self._resolve_library_id(library_type, library_id)
        url = f"/{library_type}/{library_id}/items/{item_key}/children"
        resp = await self._request("GET", url, params={"itemType": "note"})
        resp.raise_for_status()

        return [
            ZoteroItem(key=item["key"], version=item["version"], data=item["data"])
            for item in resp.json()
        ]

    async def get_collections(
        self, library_type: str, library_id: int
    ) -> list[dict]:
        """Get all collections in a library. Returns list of {key, name}."""
        library_id = await self._resolve_library_id(library_type, library_id)
        url = f"/{library_type}/{library_id}/collections"
        all_collections = []
        start = 0
        limit = 100

        while True:
            resp = await self._request(
                "GET", url, params={"start": start, "limit": limit}
            )
            resp.raise_for_status()
            items = resp.json()
            for item in items:
                all_collections.append(
                    {"key": item["key"], "name": item["data"]["name"]}
                )
            if len(items) < limit:
                break
            start += limit

        return all_collections

    async def delete_item(
        self, library_type: str, library_id: int, item_key: str, version: int
    ) -> None:
        """Delete a Zotero item."""
        library_id = await self._resolve_library_id(library_type, library_id)
        url = f"/{library_type}/{library_id}/items/{item_key}"
        resp = await self._request(
            "DELETE",
            url,
            headers={"If-Unmodified-Since-Version": str(version)},
        )
        if resp.status_code == 412:
            new_version = int(resp.headers.get("Last-Modified-Version", "0"))
            raise ZoteroConflictError(new_version)
        resp.raise_for_status()
