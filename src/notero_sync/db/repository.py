import json
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base, CollectionMap, NoteSyncState, SyncState, WebhookEvent


class Repository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init_db(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()

    # -- SyncState --

    async def get_sync_state(self, notion_page_id: str) -> SyncState | None:
        async with self._session_factory() as session:
            return await session.get(SyncState, notion_page_id)

    async def upsert_sync_state(
        self,
        notion_page_id: str,
        zotero_item_key: str,
        zotero_group_id: int,
        last_zotero_version: int,
        property_snapshot: dict,
    ) -> None:
        async with self._session_factory() as session:
            existing = await session.get(SyncState, notion_page_id)
            now = datetime.now(timezone.utc)
            if existing:
                existing.zotero_item_key = zotero_item_key
                existing.zotero_group_id = zotero_group_id
                existing.last_zotero_version = last_zotero_version
                existing.property_snapshot = property_snapshot
                existing.last_synced_at = now
                existing.deleted = False
            else:
                session.add(
                    SyncState(
                        notion_page_id=notion_page_id,
                        zotero_item_key=zotero_item_key,
                        zotero_group_id=zotero_group_id,
                        last_zotero_version=last_zotero_version,
                        property_snapshot=property_snapshot,
                        last_synced_at=now,
                    )
                )
            await session.commit()

    async def mark_deleted(self, notion_page_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(SyncState)
                .where(SyncState.notion_page_id == notion_page_id)
                .values(deleted=True)
            )
            await session.commit()

    # -- WebhookEvent --

    async def is_event_processed(self, event_id: str) -> bool:
        async with self._session_factory() as session:
            evt = await session.get(WebhookEvent, event_id)
            return evt is not None and evt.processed

    async def record_event(self, event_id: str, notion_page_id: str) -> bool:
        """Record an event. Returns False if already exists (dedup)."""
        async with self._session_factory() as session:
            existing = await session.get(WebhookEvent, event_id)
            if existing:
                return False
            session.add(
                WebhookEvent(
                    event_id=event_id,
                    notion_page_id=notion_page_id,
                )
            )
            await session.commit()
            return True

    async def mark_event_processed(self, event_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(WebhookEvent)
                .where(WebhookEvent.event_id == event_id)
                .values(processed=True)
            )
            await session.commit()

    # -- CollectionMap --

    async def get_collection_key(self, group_id: int, name: str) -> str | None:
        async with self._session_factory() as session:
            stmt = select(CollectionMap).where(
                CollectionMap.group_id == group_id,
                CollectionMap.collection_name == name,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.collection_key if row else None

    async def get_collection_name(self, group_id: int, key: str) -> str | None:
        async with self._session_factory() as session:
            stmt = select(CollectionMap).where(
                CollectionMap.group_id == group_id,
                CollectionMap.collection_key == key,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.collection_name if row else None

    async def refresh_collections(self, group_id: int, collections: list[dict]) -> None:
        """Replace all cached collections for a group."""
        async with self._session_factory() as session:
            # Delete existing
            stmt = select(CollectionMap).where(CollectionMap.group_id == group_id)
            result = await session.execute(stmt)
            for row in result.scalars():
                await session.delete(row)
            # Insert fresh
            for col in collections:
                session.add(
                    CollectionMap(
                        group_id=group_id,
                        collection_key=col["key"],
                        collection_name=col["name"],
                    )
                )
            await session.commit()

    async def get_all_collection_names(self, group_id: int) -> dict[str, str]:
        """Return {collection_key: collection_name} for a group."""
        async with self._session_factory() as session:
            stmt = select(CollectionMap).where(CollectionMap.group_id == group_id)
            result = await session.execute(stmt)
            return {row.collection_key: row.collection_name for row in result.scalars()}

    # -- NoteSyncState --

    async def get_note_sync_state(self, notion_block_id: str) -> NoteSyncState | None:
        async with self._session_factory() as session:
            return await session.get(NoteSyncState, notion_block_id)

    async def get_note_sync_states_for_parent(
        self, zotero_parent_key: str, zotero_group_id: int
    ) -> list[NoteSyncState]:
        async with self._session_factory() as session:
            stmt = select(NoteSyncState).where(
                NoteSyncState.zotero_parent_key == zotero_parent_key,
                NoteSyncState.zotero_group_id == zotero_group_id,
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def upsert_note_sync_state(
        self,
        notion_block_id: str,
        zotero_note_key: str,
        zotero_parent_key: str,
        zotero_group_id: int,
        content_hash: str,
    ) -> None:
        async with self._session_factory() as session:
            existing = await session.get(NoteSyncState, notion_block_id)
            now = datetime.now(timezone.utc)
            if existing:
                existing.zotero_note_key = zotero_note_key
                existing.content_hash = content_hash
                existing.last_synced_at = now
            else:
                session.add(
                    NoteSyncState(
                        notion_block_id=notion_block_id,
                        zotero_note_key=zotero_note_key,
                        zotero_parent_key=zotero_parent_key,
                        zotero_group_id=zotero_group_id,
                        content_hash=content_hash,
                        last_synced_at=now,
                    )
                )
            await session.commit()

    async def delete_note_sync_state(self, notion_block_id: str) -> None:
        async with self._session_factory() as session:
            existing = await session.get(NoteSyncState, notion_block_id)
            if existing:
                await session.delete(existing)
                await session.commit()
