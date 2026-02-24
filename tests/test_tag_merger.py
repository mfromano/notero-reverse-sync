from notero_sync.sync.tag_merger import three_way_merge


def test_no_changes():
    base = ["A", "B", "C"]
    result = three_way_merge(base, base.copy(), base.copy())
    assert set(result) == {"A", "B", "C"}


def test_notion_adds():
    base = ["A", "B", "C"]
    notion = ["A", "B", "C", "D"]
    zotero = ["A", "B", "C"]
    result = three_way_merge(base, notion, zotero)
    assert set(result) == {"A", "B", "C", "D"}


def test_notion_removes():
    base = ["A", "B", "C"]
    notion = ["A", "C"]
    zotero = ["A", "B", "C"]
    result = three_way_merge(base, notion, zotero)
    assert set(result) == {"A", "C"}


def test_zotero_adds():
    base = ["A", "B", "C"]
    notion = ["A", "B", "C"]
    zotero = ["A", "B", "C", "E"]
    result = three_way_merge(base, notion, zotero)
    assert set(result) == {"A", "B", "C", "E"}


def test_both_add_different():
    """Notion adds D, Zotero adds E → both present."""
    base = ["A", "B", "C"]
    notion = ["A", "B", "C", "D"]
    zotero = ["A", "B", "C", "E"]
    result = three_way_merge(base, notion, zotero)
    assert set(result) == {"A", "B", "C", "D", "E"}


def test_notion_removes_zotero_adds():
    """Notion removes B, Zotero adds E → result has no B, has E."""
    base = ["A", "B", "C"]
    notion = ["A", "C", "D"]
    zotero = ["A", "B", "C", "E"]
    result = three_way_merge(base, notion, zotero)
    assert set(result) == {"A", "C", "D", "E"}


def test_preserve_values():
    """Preserved values stay even if both sides try to remove them."""
    base = ["A", "B", "notion"]
    notion = ["A", "B"]  # removed "notion"
    zotero = ["A", "B"]
    result = three_way_merge(base, notion, zotero, preserve={"notion"})
    assert "notion" in result


def test_empty_base():
    """First sync — no base. Everything in Notion is 'added'."""
    result = three_way_merge([], ["A", "B"], ["C"])
    assert set(result) == {"A", "B", "C"}


def test_all_empty():
    assert three_way_merge([], [], []) == []


def test_both_remove_same():
    """Both sides remove B → B is gone."""
    base = ["A", "B", "C"]
    notion = ["A", "C"]
    zotero = ["A", "C"]
    result = three_way_merge(base, notion, zotero)
    assert set(result) == {"A", "C"}


def test_stable_order():
    """Result preserves Zotero's order for existing items."""
    base = ["A", "B"]
    notion = ["A", "B", "D"]
    zotero = ["C", "A", "B"]  # C first in Zotero
    result = three_way_merge(base, notion, zotero)
    # C, A, B should come first (Zotero order), then D (new)
    assert result == ["C", "A", "B", "D"]
