"""Tests for the sync engine merge logic."""

import pytest

from notero_sync.sync.engine import SyncEngine
from notero_sync.sync.field_map import FIELD_MAP_BY_NOTION, FieldMapping, MergeStrategy


class TestScalarMerge:
    """Test _merge_scalar_field logic."""

    def _make_engine(self):
        return SyncEngine(None, None, None, None)

    def _field(self, notion_name: str = "Abstract", zotero_field: str = "abstractNote"):
        return FieldMapping(notion_name, zotero_field, MergeStrategy.SCALAR)

    def test_no_change(self):
        engine = self._make_engine()
        f = self._field()
        result = engine._merge_scalar_field(f, "same", {"abstractNote": "same"}, {"Abstract": "same"})
        assert result is None

    def test_notion_changed_only(self):
        engine = self._make_engine()
        f = self._field()
        result = engine._merge_scalar_field(
            f, "new value", {"abstractNote": "old"}, {"Abstract": "old"}
        )
        assert result == "new value"

    def test_zotero_changed_only(self):
        engine = self._make_engine()
        f = self._field()
        result = engine._merge_scalar_field(
            f, "old", {"abstractNote": "zotero changed"}, {"Abstract": "old"}
        )
        assert result is None  # Notion didn't change

    def test_both_changed_zotero_wins(self):
        engine = self._make_engine()
        f = self._field()
        result = engine._merge_scalar_field(
            f, "notion changed", {"abstractNote": "zotero changed"}, {"Abstract": "base"}
        )
        assert result is None  # Zotero wins on conflict

    def test_notion_clears_value(self):
        engine = self._make_engine()
        f = self._field()
        result = engine._merge_scalar_field(
            f, "", {"abstractNote": "old"}, {"Abstract": "old"}
        )
        assert result == ""  # Notion cleared it

    def test_notion_sets_from_empty(self):
        engine = self._make_engine()
        f = self._field()
        result = engine._merge_scalar_field(
            f, "new value", {"abstractNote": ""}, {"Abstract": ""}
        )
        assert result == "new value"


class TestBuildSnapshot:
    def test_snapshot_includes_syncable_fields(self):
        engine = SyncEngine(None, None, None, None)
        props = {
            "Tags": ["tag1", "tag2"],
            "Abstract": "An abstract",
            "Title": "A title",  # Not in FIELD_MAP_BY_NOTION
        }
        snapshot = engine._build_snapshot(props)
        assert "Tags" in snapshot
        assert "Abstract" in snapshot
        assert "Title" not in snapshot

    def test_snapshot_empty_when_no_matching_fields(self):
        engine = SyncEngine(None, None, None, None)
        snapshot = engine._build_snapshot({"Unknown": "value"})
        assert snapshot == {}
