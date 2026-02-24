/* Parse Notion property values into plain JS types. */

function parsePropertyValue(prop) {
  const propType = prop.type;

  if (propType === "title") {
    const parts = prop.title || [];
    const text = parts.map((t) => t.plain_text || "").join("");
    return text || null;
  }

  if (propType === "rich_text") {
    const parts = prop.rich_text || [];
    const text = parts.map((t) => t.plain_text || "").join("");
    return text || null;
  }

  if (propType === "url") {
    return prop.url || null;
  }

  if (propType === "select") {
    return prop.select ? prop.select.name : null;
  }

  if (propType === "multi_select") {
    const items = prop.multi_select || [];
    return items.map((item) => item.name);
  }

  if (propType === "number") {
    return prop.number;
  }

  if (propType === "checkbox") {
    return prop.checkbox;
  }

  if (propType === "date") {
    const dateObj = prop.date;
    return dateObj ? dateObj.start || null : null;
  }

  return null;
}

function extractSyncableProperties(properties, zoteroUriField = "Zotero URI") {
  const result = {};

  for (const [name, prop] of Object.entries(properties)) {
    if (name === zoteroUriField) {
      result.zotero_uri = parsePropertyValue(prop);
      continue;
    }

    const key = name.trim();
    const value = parsePropertyValue(prop);
    if (value !== null && value !== undefined) {
      result[key] = value;
    }
  }

  return result;
}
