/* Convert Notion blocks to Zotero-compatible HTML. */

function _escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function richTextToHtml(richTexts) {
  const parts = [];
  for (const rt of richTexts) {
    let text = _escapeHtml(rt.plain_text || "");
    const ann = rt.annotations || {};
    const href = rt.href;

    if (ann.code) text = `<code>${text}</code>`;
    if (ann.bold) text = `<strong>${text}</strong>`;
    if (ann.italic) text = `<em>${text}</em>`;
    if (ann.underline) text = `<u>${text}</u>`;
    if (ann.strikethrough) text = `<s>${text}</s>`;
    if (href) text = `<a href="${_escapeHtml(href)}">${text}</a>`;

    parts.push(text);
  }
  return parts.join("");
}

function _blockToHtml(block) {
  const blockType = block.type || "";
  const blockData = block[blockType] || {};
  const richText = blockData.rich_text || [];
  const content = richTextToHtml(richText);

  if (blockType === "paragraph") return content ? `<p>${content}</p>` : "<p></p>";
  if (blockType === "heading_1") return `<h1>${content}</h1>`;
  if (blockType === "heading_2") return `<h2>${content}</h2>`;
  if (blockType === "heading_3") return `<h3>${content}</h3>`;
  if (blockType === "bulleted_list_item") return `<li>${content}</li>`;
  if (blockType === "numbered_list_item") return `<li>${content}</li>`;
  if (blockType === "to_do") {
    const checked = blockData.checked ? "checked " : "";
    return `<li><input type="checkbox" ${checked}disabled />${content}</li>`;
  }
  if (blockType === "quote") return `<blockquote>${content}</blockquote>`;
  if (blockType === "code") return `<pre><code>${content}</code></pre>`;
  if (blockType === "divider") return "<hr />";
  if (blockType === "callout") return `<p>${content}</p>`;
  if (content) return `<p>${content}</p>`;
  return "";
}

function blocksToHtml(blocks) {
  const htmlParts = [];
  let listBuffer = [];
  let listType = null;

  function flushList() {
    if (listBuffer.length && listType) {
      htmlParts.push(`<${listType}>${listBuffer.join("")}</${listType}>`);
      listBuffer = [];
      listType = null;
    }
  }

  for (const block of blocks) {
    const bt = block.type || "";

    if (bt === "bulleted_list_item") {
      if (listType !== "ul") { flushList(); listType = "ul"; }
      listBuffer.push(_blockToHtml(block));
    } else if (bt === "numbered_list_item") {
      if (listType !== "ol") { flushList(); listType = "ol"; }
      listBuffer.push(_blockToHtml(block));
    } else if (bt === "to_do") {
      if (listType !== "ul") { flushList(); listType = "ul"; }
      listBuffer.push(_blockToHtml(block));
    } else {
      flushList();
      const html = _blockToHtml(block);
      if (html) htmlParts.push(html);
    }
  }

  flushList();
  return htmlParts.join("\n");
}

function computeBlocksHash(blocks) {
  const contentParts = blocks.map((block) => {
    const bt = block.type || "";
    const blockData = block[bt] || {};
    return {
      type: bt,
      rich_text: blockData.rich_text || [],
      checked: blockData.checked || null,
    };
  });
  const serialized = JSON.stringify(contentParts);

  // Use XPCOM nsICryptoHash (available in all Zotero contexts)
  const converter = Components.classes["@mozilla.org/intl/scriptableunicodeconverter"]
    .createInstance(Components.interfaces.nsIScriptableUnicodeConverter);
  converter.charset = "UTF-8";
  const data = converter.convertToByteArray(serialized, {});
  const hasher = Components.classes["@mozilla.org/security/hash;1"]
    .createInstance(Components.interfaces.nsICryptoHash);
  hasher.init(hasher.SHA256);
  hasher.update(data, data.length);
  const hash = hasher.finish(false);
  return Array.from(hash, (c) => ("0" + c.charCodeAt(0).toString(16)).slice(-2)).join("");
}
