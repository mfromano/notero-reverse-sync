/* global Zotero */

/**
 * Timer-based polling of Notion for changes.
 * Replaces the webhook server from the Python version.
 */
class PollingScheduler {
  constructor(syncEngine, noteSyncEngine, notionClient, stateStore) {
    this._syncEngine = syncEngine;
    this._noteSyncEngine = noteSyncEngine;
    this._notion = notionClient;
    this._store = stateStore;
    this._timerId = null;
    this._running = false;
  }

  get _groupId() {
    return Zotero.Prefs.get("extensions.notero-reverse-sync.zoteroGroupId", true) || 0;
  }

  get _intervalMs() {
    const minutes =
      Zotero.Prefs.get("extensions.notero-reverse-sync.pollIntervalMinutes", true) || 5;
    return minutes * 60 * 1000;
  }

  get _deleteOrphaned() {
    return Zotero.Prefs.get("extensions.notero-reverse-sync.deleteOrphanedNotes", true) || false;
  }

  start() {
    if (this._timerId) return;

    // Delay first poll to let Zotero finish loading
    this._timerId = Zotero.setTimeout(() => {
      this._poll();
      this._timerId = Zotero.setInterval(() => this._poll(), this._intervalMs);
    }, 15000);

    NRSLog.info(`Polling scheduler started (interval: ${this._intervalMs / 1000}s)`);
  }

  stop() {
    if (this._timerId) {
      Zotero.clearTimeout(this._timerId);
      Zotero.clearInterval(this._timerId);
      this._timerId = null;
    }
    NRSLog.info("Polling scheduler stopped");
  }

  /**
   * Run a single poll cycle. Can be called manually for "Sync Now".
   */
  async poll() {
    return this._poll();
  }

  async _poll() {
    if (this._running) {
      NRSLog.debug("Poll already in progress, skipping");
      return;
    }

    const groupId = this._groupId;
    if (!groupId) {
      NRSLog.debug("No group ID configured, skipping poll");
      return;
    }

    this._running = true;

    try {
      const lastPoll = this._store.getLastPollTime();
      let pages;

      if (lastPoll) {
        NRSLog.info(`Polling Notion for changes since ${lastPoll}`);
        pages = await this._notion.queryRecentlyModified(lastPoll);
      } else {
        NRSLog.info("First poll: fetching all pages");
        pages = await this._notion.queryAllPages();
      }

      const newPollTime = new Date().toISOString();
      let synced = 0;

      for (const page of pages) {
        const pageId = page.id;
        const properties = page.properties || {};
        const parsed = extractSyncableProperties(properties);

        const relevant = parsed["Relevant?"];
        if (relevant !== "Yes" && relevant !== "Highly") continue;

        const zoteroUri = parsed.zotero_uri;
        if (!zoteroUri) continue;

        const ref = parseZoteroUri(zoteroUri);
        if (!ref) continue;

        // Only sync pages that have been bootstrapped
        const syncState = this._store.getSyncState(pageId);
        if (!syncState) continue;

        try {
          // Sync properties
          await this._syncEngine.syncPageProperties(pageId, groupId);

          // Sync notes
          await this._noteSyncEngine.syncPageNotes(pageId, groupId, syncState.zoteroItemKey);

          synced++;
        } catch (e) {
          NRSLog.error(`Error syncing page ${pageId}: ${e.message}`);
        }
      }

      this._store.setLastPollTime(newPollTime);
      await this._store.save();
      NRSLog.info(`Poll complete: ${pages.length} pages checked, ${synced} synced`);
    } catch (e) {
      NRSLog.error(`Poll error: ${e.message}`);
    } finally {
      this._running = false;
    }
  }
}
