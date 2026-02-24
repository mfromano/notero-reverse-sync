/* global Zotero */

/**
 * Resolve collection names <-> keys, with caching.
 */
class CollectionResolver {
  constructor(stateStore) {
    this._store = stateStore;
    this._lastRefresh = {};
  }

  ensureCache(groupId) {
    const last = this._lastRefresh[groupId] || 0;
    if (Date.now() - last < 600000) return; // 10 min TTL

    NRSLog.info(`Refreshing collection cache for group ${groupId}`);
    const collections = ZoteroItemBridge.getCollections(groupId);
    this._store.refreshCollections(groupId, collections);
    this._lastRefresh[groupId] = Date.now();
  }

  namesToKeys(groupId, names) {
    this.ensureCache(groupId);
    const keys = [];
    for (const name of names) {
      const key = this._store.getCollectionKey(groupId, name);
      if (key) {
        keys.push(key);
      } else {
        NRSLog.warn(`Collection name '${name}' not found in group ${groupId}`);
      }
    }
    return keys;
  }

  keysToNames(groupId, keys) {
    this.ensureCache(groupId);
    const names = [];
    for (const key of keys) {
      const name = this._store.getCollectionName(groupId, key);
      if (name) {
        names.push(name);
      } else {
        NRSLog.warn(`Collection key '${key}' not found in group ${groupId}`);
      }
    }
    return names;
  }
}
