"""Convert Notion blocks to Zotero-compatible HTML."""

import hashlib
import json
from html import escape


def rich_text_to_html(rich_texts: list[dict]) -> str:
    """Convert Notion rich text array to HTML string."""
    parts = []
    for rt in rich_texts:
        text = escape(rt.get("plain_text", ""))
        annotations = rt.get("annotations", {})
        href = rt.get("href")

        if annotations.get("code"):
            text = f"<code>{text}</code>"
        if annotations.get("bold"):
            text = f"<strong>{text}</strong>"
        if annotations.get("italic"):
            text = f"<em>{text}</em>"
        if annotations.get("underline"):
            text = f"<u>{text}</u>"
        if annotations.get("strikethrough"):
            text = f"<s>{text}</s>"
        if href:
            text = f'<a href="{escape(href)}">{text}</a>'

        parts.append(text)
    return "".join(parts)


def _block_to_html(block: dict) -> str:
    """Convert a single Notion block to an HTML string."""
    block_type = block.get("type", "")
    block_data = block.get(block_type, {})
    rich_text = block_data.get("rich_text", [])
    content = rich_text_to_html(rich_text)

    if block_type == "paragraph":
        return f"<p>{content}</p>" if content else "<p></p>"

    if block_type == "heading_1":
        return f"<h1>{content}</h1>"

    if block_type == "heading_2":
        return f"<h2>{content}</h2>"

    if block_type == "heading_3":
        return f"<h3>{content}</h3>"

    if block_type == "bulleted_list_item":
        return f"<li>{content}</li>"

    if block_type == "numbered_list_item":
        return f"<li>{content}</li>"

    if block_type == "to_do":
        checked = block_data.get("checked", False)
        checkbox = "checked " if checked else ""
        return f'<li><input type="checkbox" {checkbox}disabled />{content}</li>'

    if block_type == "quote":
        return f"<blockquote>{content}</blockquote>"

    if block_type == "code":
        language = block_data.get("language", "")
        return f"<pre><code>{content}</code></pre>"

    if block_type == "divider":
        return "<hr />"

    if block_type == "callout":
        return f"<p>{content}</p>"

    # Unsupported block type - render as paragraph if it has content
    if content:
        return f"<p>{content}</p>"
    return ""


def blocks_to_html(blocks: list[dict]) -> str:
    """Convert a list of Notion blocks to a Zotero-compatible HTML string.

    Handles list grouping: consecutive bulleted_list_item blocks are wrapped
    in <ul>, consecutive numbered_list_item blocks are wrapped in <ol>.
    """
    html_parts = []
    list_buffer: list[str] = []
    list_type: str | None = None  # "ul" or "ol"

    def flush_list():
        nonlocal list_buffer, list_type
        if list_buffer and list_type:
            html_parts.append(f"<{list_type}>{''.join(list_buffer)}</{list_type}>")
            list_buffer = []
            list_type = None

    for block in blocks:
        bt = block.get("type", "")

        if bt == "bulleted_list_item":
            if list_type != "ul":
                flush_list()
                list_type = "ul"
            list_buffer.append(_block_to_html(block))
        elif bt == "numbered_list_item":
            if list_type != "ol":
                flush_list()
                list_type = "ol"
            list_buffer.append(_block_to_html(block))
        elif bt == "to_do":
            if list_type != "ul":
                flush_list()
                list_type = "ul"
            list_buffer.append(_block_to_html(block))
        else:
            flush_list()
            html = _block_to_html(block)
            if html:
                html_parts.append(html)

    flush_list()
    return "\n".join(html_parts)


def compute_blocks_hash(blocks: list[dict]) -> str:
    """Compute a SHA-256 hash of block content for change detection."""
    # Serialize only the content-relevant parts of each block
    content_parts = []
    for block in blocks:
        bt = block.get("type", "")
        block_data = block.get(bt, {})
        content_parts.append({
            "type": bt,
            "rich_text": block_data.get("rich_text", []),
            "checked": block_data.get("checked"),
        })
    serialized = json.dumps(content_parts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()
