from notero_sync.notion.block_parser import blocks_to_html, compute_blocks_hash, rich_text_to_html


def _rt(text: str, **annotations) -> dict:
    """Helper to create a Notion rich text object."""
    return {
        "plain_text": text,
        "annotations": annotations,
        "href": annotations.pop("href", None),
    }


def _block(block_type: str, rich_text: list[dict] | None = None, **extra) -> dict:
    data = {}
    if rich_text is not None:
        data["rich_text"] = rich_text
    data.update(extra)
    return {"type": block_type, block_type: data}


class TestRichTextToHtml:
    def test_plain_text(self):
        assert rich_text_to_html([_rt("hello")]) == "hello"

    def test_bold(self):
        assert rich_text_to_html([_rt("bold", bold=True)]) == "<strong>bold</strong>"

    def test_italic(self):
        assert rich_text_to_html([_rt("em", italic=True)]) == "<em>em</em>"

    def test_underline(self):
        assert rich_text_to_html([_rt("u", underline=True)]) == "<u>u</u>"

    def test_strikethrough(self):
        assert rich_text_to_html([_rt("s", strikethrough=True)]) == "<s>s</s>"

    def test_code(self):
        assert rich_text_to_html([_rt("x", code=True)]) == "<code>x</code>"

    def test_link(self):
        rt = {"plain_text": "click", "annotations": {}, "href": "https://example.com"}
        assert rich_text_to_html([rt]) == '<a href="https://example.com">click</a>'

    def test_combined_annotations(self):
        result = rich_text_to_html([_rt("text", bold=True, italic=True)])
        assert "<strong>" in result
        assert "<em>" in result

    def test_multiple_segments(self):
        result = rich_text_to_html([_rt("hello "), _rt("world", bold=True)])
        assert result == "hello <strong>world</strong>"

    def test_html_escaping(self):
        assert rich_text_to_html([_rt("<script>")]) == "&lt;script&gt;"


class TestBlocksToHtml:
    def test_paragraph(self):
        blocks = [_block("paragraph", [_rt("Hello world")])]
        assert blocks_to_html(blocks) == "<p>Hello world</p>"

    def test_heading_1(self):
        blocks = [_block("heading_1", [_rt("Title")])]
        assert blocks_to_html(blocks) == "<h1>Title</h1>"

    def test_heading_2(self):
        blocks = [_block("heading_2", [_rt("Subtitle")])]
        assert blocks_to_html(blocks) == "<h2>Subtitle</h2>"

    def test_heading_3(self):
        blocks = [_block("heading_3", [_rt("Section")])]
        assert blocks_to_html(blocks) == "<h3>Section</h3>"

    def test_bulleted_list(self):
        blocks = [
            _block("bulleted_list_item", [_rt("item 1")]),
            _block("bulleted_list_item", [_rt("item 2")]),
        ]
        result = blocks_to_html(blocks)
        assert result == "<ul><li>item 1</li><li>item 2</li></ul>"

    def test_numbered_list(self):
        blocks = [
            _block("numbered_list_item", [_rt("first")]),
            _block("numbered_list_item", [_rt("second")]),
        ]
        result = blocks_to_html(blocks)
        assert result == "<ol><li>first</li><li>second</li></ol>"

    def test_todo(self):
        blocks = [_block("to_do", [_rt("task")], checked=True)]
        result = blocks_to_html(blocks)
        assert "checkbox" in result
        assert "checked" in result
        assert "task" in result

    def test_quote(self):
        blocks = [_block("quote", [_rt("quoted text")])]
        assert blocks_to_html(blocks) == "<blockquote>quoted text</blockquote>"

    def test_code_block(self):
        blocks = [_block("code", [_rt("print('hi')")])]
        result = blocks_to_html(blocks)
        assert result == "<pre><code>print(&#x27;hi&#x27;)</code></pre>"

    def test_divider(self):
        blocks = [_block("divider")]
        assert blocks_to_html(blocks) == "<hr />"

    def test_mixed_content(self):
        blocks = [
            _block("heading_2", [_rt("Notes")]),
            _block("paragraph", [_rt("Some text")]),
            _block("bulleted_list_item", [_rt("point 1")]),
            _block("bulleted_list_item", [_rt("point 2")]),
            _block("paragraph", [_rt("More text")]),
        ]
        result = blocks_to_html(blocks)
        assert "<h2>Notes</h2>" in result
        assert "<ul>" in result
        assert "</ul>" in result
        assert result.count("<ul>") == 1

    def test_list_type_transition(self):
        blocks = [
            _block("bulleted_list_item", [_rt("bullet")]),
            _block("numbered_list_item", [_rt("number")]),
        ]
        result = blocks_to_html(blocks)
        assert "<ul><li>bullet</li></ul>" in result
        assert "<ol><li>number</li></ol>" in result


class TestComputeBlocksHash:
    def test_same_content_same_hash(self):
        blocks = [_block("paragraph", [_rt("hello")])]
        h1 = compute_blocks_hash(blocks)
        h2 = compute_blocks_hash(blocks)
        assert h1 == h2

    def test_different_content_different_hash(self):
        b1 = [_block("paragraph", [_rt("hello")])]
        b2 = [_block("paragraph", [_rt("world")])]
        assert compute_blocks_hash(b1) != compute_blocks_hash(b2)

    def test_ignores_non_content_fields(self):
        b1 = [{"type": "paragraph", "paragraph": {"rich_text": [_rt("hello")]}, "id": "aaa"}]
        b2 = [{"type": "paragraph", "paragraph": {"rich_text": [_rt("hello")]}, "id": "bbb"}]
        assert compute_blocks_hash(b1) == compute_blocks_hash(b2)
