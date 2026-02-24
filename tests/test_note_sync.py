"""Tests for the note sync engine."""

import pytest

from notero_sync.sync.note_sync import NoteSyncEngine, ZOTERO_NOTES_HEADING


def _heading(level: int, text: str) -> dict:
    ht = f"heading_{level}"
    return {
        "id": f"heading-{text.lower().replace(' ', '-')}",
        "type": ht,
        ht: {"rich_text": [{"plain_text": text}]},
        "has_children": False,
    }


def _paragraph(text: str, block_id: str = "block-1") -> dict:
    return {
        "id": block_id,
        "type": "paragraph",
        "paragraph": {"rich_text": [{"plain_text": text}]},
        "has_children": False,
    }


class TestExtractNoteSections:
    """Test the _extract_note_sections method."""

    def _make_engine(self):
        # Create engine with None clients — we only test the parsing method
        return NoteSyncEngine(None, None, None)

    def test_no_heading(self):
        engine = self._make_engine()
        blocks = [_paragraph("text"), _paragraph("more text", "block-2")]
        sections = engine._extract_note_sections(blocks)
        assert sections == []

    def test_heading_with_notes(self):
        engine = self._make_engine()
        blocks = [
            _heading(2, ZOTERO_NOTES_HEADING),
            _paragraph("note 1", "n1"),
            _paragraph("note 2", "n2"),
        ]
        sections = engine._extract_note_sections(blocks)
        assert len(sections) == 2
        assert sections[0]["block_id"] == "n1"
        assert sections[1]["block_id"] == "n2"

    def test_heading_ends_at_next_heading(self):
        engine = self._make_engine()
        blocks = [
            _heading(2, ZOTERO_NOTES_HEADING),
            _paragraph("note 1", "n1"),
            _heading(2, "Other Section"),
            _paragraph("not a note", "n2"),
        ]
        sections = engine._extract_note_sections(blocks)
        assert len(sections) == 1
        assert sections[0]["block_id"] == "n1"

    def test_content_before_heading_ignored(self):
        engine = self._make_engine()
        blocks = [
            _paragraph("before", "b1"),
            _heading(2, ZOTERO_NOTES_HEADING),
            _paragraph("note", "n1"),
        ]
        sections = engine._extract_note_sections(blocks)
        assert len(sections) == 1
        assert sections[0]["block_id"] == "n1"

    def test_different_heading_levels(self):
        engine = self._make_engine()
        for level in (1, 2, 3):
            blocks = [
                _heading(level, ZOTERO_NOTES_HEADING),
                _paragraph("note", "n1"),
            ]
            sections = engine._extract_note_sections(blocks)
            assert len(sections) == 1
