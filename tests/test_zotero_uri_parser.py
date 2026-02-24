from notero_sync.utils.zotero_uri import ZoteroItemRef, parse_zotero_uri


def test_parse_group_uri():
    ref = parse_zotero_uri("https://www.zotero.org/groups/483726/items/A5X7AKTH")
    assert ref == ZoteroItemRef(library_type="groups", library_id=483726, item_key="A5X7AKTH")


def test_parse_user_uri():
    ref = parse_zotero_uri("https://zotero.org/users/12345/items/ABCD1234")
    assert ref == ZoteroItemRef(library_type="users", library_id=12345, item_key="ABCD1234")


def test_parse_uri_without_www():
    ref = parse_zotero_uri("https://zotero.org/groups/999/items/ZZZZ0000")
    assert ref is not None
    assert ref.library_id == 999
    assert ref.item_key == "ZZZZ0000"


def test_parse_invalid_uri():
    assert parse_zotero_uri("https://google.com") is None
    assert parse_zotero_uri("not a url") is None
    assert parse_zotero_uri("") is None


def test_parse_uri_embedded_in_text():
    text = "See https://www.zotero.org/groups/100/items/KEY12345 for details"
    ref = parse_zotero_uri(text)
    assert ref is not None
    assert ref.item_key == "KEY12345"


def test_api_base():
    ref = ZoteroItemRef(library_type="groups", library_id=483726, item_key="A5X7AKTH")
    assert ref.api_base == "https://api.zotero.org/groups/483726"


def test_item_url():
    ref = ZoteroItemRef(library_type="groups", library_id=483726, item_key="A5X7AKTH")
    assert ref.item_url == "https://api.zotero.org/groups/483726/items/A5X7AKTH"
