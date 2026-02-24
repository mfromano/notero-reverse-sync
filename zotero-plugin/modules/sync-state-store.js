/* global Zotero, IOUtils, PathUtils */

/**
 * JSON-file-based sync state persistence.
 * Stores in the Zotero data directory.
 */
class SyncStateStore {
  constructor() {
    this._filePath = null;
    this._data = {
      syncStates: {},
      noteSyncStates: {},
      collectionMap: {},
      lastPollTime: null,
    };
  }

  async load() {
    this._filePath = PathUtils.join(Zotero.DataDirectory.dir, "notero-reverse-sync-state.json");
    try {
      const raw = await Zotero.File.getContentsAsync(this._filePath);
      this._data = JSON.parse(raw);
    } catch (e) {
      // File doesn't exist yet or is corrupted - start fresh
      NRSLog.info("No existing state file, starting fresh");
    }
  }

  async save() {
    const json = JSON.stringify(this._data, null, 2);
    await Zotero.File.putContentsAsync(this._filePath, json);
  }

  saveSync() {
    try {
      const json = JSON.stringify(this._data, null, 2);
      Zotero.File.putContents(Zotero.File.pathToFile(this._filePath), json);
    } catch (e) {
      NRSLog.error("Failed to save state synchronously: " + e.message);
    }
  }

  // --- SyncState ---

  getSyncState(notionPageId) {
    return this._data.syncStates[notionPageId] || null;
  }

  upsertSyncState(notionPageId, state) {
    this._data.syncStates[notionPageId] = state;
  }

  markDeleted(notionPageId) {
    const state = this._data.syncStates[notionPageId];
    if (state) {
      state.deleted = true;
    }
  }

  // --- NoteSyncState ---

  getNoteSyncState(notionBlockId) {
    return this._data.noteSyncStates[notionBlockId] || null;
  }

  getNoteSyncStatesForParent(zoteroParentKey, zoteroGroupId) {
    const results = [];
    for (const [blockId, state] of Object.entries(this._data.noteSyncStates)) {
      if (state.zoteroParentKey === zoteroParentKey && state.zoteroGroupId === zoteroGroupId) {
        results.push({ notionBlockId: blockId, ...state });
      }
    }
    return results;
  }

  upsertNoteSyncState(notionBlockId, state) {
    this._data.noteSyncStates[notionBlockId] = state;
  }

  deleteNoteSyncState(notionBlockId) {
    delete this._data.noteSyncStates[notionBlockId];
  }

  // --- CollectionMap ---

  getCollectionKey(groupId, name) {
    const map = this._data.collectionMap[groupId];
    if (!map) return null;
    for (const [key, n] of Object.entries(map)) {
      if (n === name) return key;
    }
    return null;
  }

  getCollectionName(groupId, key) {
    const map = this._data.collectionMap[groupId];
    return map ? map[key] || null : null;
  }

  refreshCollections(groupId, collections) {
    const map = {};
    for (const c of collections) {
      map[c.key] = c.name;
    }
    this._data.collectionMap[groupId] = map;
  }

  // --- Poll tracking ---

  getLastPollTime() {
    return this._data.lastPollTime;
  }

  setLastPollTime(isoString) {
    this._data.lastPollTime = isoString;
  }
}
