/* global Zotero */

/**
 * Notion API client using Zotero.HTTP.request().
 * Reads config from Zotero preferences.
 */
class NotionAPIClient {
  get _apiKey() {
    return Zotero.Prefs.get("extensions.notero-reverse-sync.notionApiKey", true);
  }

  get _databaseId() {
    return Zotero.Prefs.get("extensions.notero-reverse-sync.notionDatabaseId", true);
  }

  async _request(method, path, body = null) {
    const url = `https://api.notion.com/v1${path}`;
    const options = {
      headers: {
        Authorization: `Bearer ${this._apiKey}`,
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
      responseType: "json",
    };

    const response = await Zotero.HTTP.request(method, url, options);

    if (response.status >= 400) {
      throw new Error(`Notion API error ${response.status}: ${response.responseText}`);
    }

    return typeof response.response === "string"
      ? JSON.parse(response.response)
      : response.response;
  }

  async getPage(pageId) {
    return this._request("GET", `/pages/${pageId}`);
  }

  async getPageProperties(pageId) {
    const page = await this.getPage(pageId);
    return page.properties || {};
  }

  async getBlockChildren(blockId, recursive = false) {
    const blocks = [];
    let cursor = null;

    do {
      const params = cursor ? `?page_size=100&start_cursor=${cursor}` : "?page_size=100";
      const data = await this._request("GET", `/blocks/${blockId}/children${params}`);
      blocks.push(...data.results);
      cursor = data.has_more ? data.next_cursor : null;
    } while (cursor);

    if (recursive) {
      for (const block of blocks) {
        if (block.has_children) {
          block.children = await this.getBlockChildren(block.id, true);
        }
      }
    }

    return blocks;
  }

  async queryDatabase(startCursor = null, pageSize = 100) {
    const body = { page_size: pageSize };
    if (startCursor) body.start_cursor = startCursor;
    return this._request("POST", `/databases/${this._databaseId}/query`, body);
  }

  async queryAllPages() {
    const pages = [];
    let cursor = null;
    do {
      const result = await this.queryDatabase(cursor);
      pages.push(...result.results);
      cursor = result.has_more ? result.next_cursor : null;
    } while (cursor);
    return pages;
  }

  /**
   * Query pages modified since a given ISO timestamp.
   * Uses Notion's last_edited_time filter to minimize API calls.
   */
  async queryRecentlyModified(sinceIso) {
    const pages = [];
    let cursor = null;
    do {
      const body = {
        page_size: 100,
        filter: {
          timestamp: "last_edited_time",
          last_edited_time: { on_or_after: sinceIso },
        },
      };
      if (cursor) body.start_cursor = cursor;
      const result = await this._request(
        "POST",
        `/databases/${this._databaseId}/query`,
        body,
      );
      pages.push(...result.results);
      cursor = result.has_more ? result.next_cursor : null;
    } while (cursor);
    return pages;
  }
}
