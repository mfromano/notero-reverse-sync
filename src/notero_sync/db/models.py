from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SyncState(Base):
    __tablename__ = "sync_state"

    notion_page_id: Mapped[str] = mapped_column(String, primary_key=True)
    zotero_item_key: Mapped[str] = mapped_column(String, nullable=False)
    zotero_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_zotero_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    property_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CollectionMap(Base):
    __tablename__ = "collection_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_key: Mapped[str] = mapped_column(String, nullable=False)
    collection_name: Mapped[str] = mapped_column(String, nullable=False)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    notion_page_id: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class NoteSyncState(Base):
    __tablename__ = "note_sync_state"

    notion_block_id: Mapped[str] = mapped_column(String, primary_key=True)
    zotero_note_key: Mapped[str] = mapped_column(String, nullable=False)
    zotero_parent_key: Mapped[str] = mapped_column(String, nullable=False)
    zotero_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
