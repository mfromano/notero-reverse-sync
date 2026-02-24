/* global Zotero */

/**
 * Property sync engine: three-way merge from Notion to Zotero.
 * Port of sync/engine.py.
 */
class PropertySyncEngine {
  constructor(stateStore, notionClient, collectionResolver) {
    this._store = stateStore;
    this._notion = notionClient;
    this._collections = collectionResolver;
  }

  async syncPageProperties(notionPageId, groupId) {
    // 1. Fetch page properties from Notion
    const properties = await this._notion.getPageProperties(notionPageId);
    const parsed = extractSyncableProperties(properties);

    // 2. Check relevance filter
    const relevant = parsed["Relevant?"];
    if (relevant !== "Yes" && relevant !== "Highly") {
      NRSLog.debug(`Page ${notionPageId} has Relevant=${relevant}, skipping`);
      return;
    }

    // 3. Extract Zotero URI and find group item key
    const zoteroUri = parsed.zotero_uri;
    if (!zoteroUri) {
      NRSLog.warn(`Page ${notionPageId} has no Zotero URI, skipping`);
      return;
    }

    // 4. Load sync state to get the group item key
    const syncState = this._store.getSyncState(notionPageId);
    if (!syncState) {
      NRSLog.debug(`Page ${notionPageId} has no sync state (not bootstrapped), skipping`);
      return;
    }
    if (syncState.deleted) {
      NRSLog.debug(`Page ${notionPageId} is marked deleted, skipping`);
      return;
    }

    const itemKey = syncState.zoteroItemKey;
    const baseSnapshot = syncState.propertySnapshot || {};

    // 5. Compute merge and patch
    await this._doMergeAndPatch(notionPageId, groupId, itemKey, parsed, baseSnapshot);
  }

  async _doMergeAndPatch(notionPageId, groupId, itemKey, notionProps, baseSnapshot) {
    const patchData = {};

    for (const [notionName, fieldMapping] of Object.entries(FIELD_MAP_BY_NOTION)) {
      const notionValue = notionProps[notionName];
      if (notionValue === undefined) continue;

      if (fieldMapping.mergeStrategy === MergeStrategy.THREE_WAY) {
        const merged = await this._mergeArrayField(
          fieldMapping, notionValue, groupId, itemKey, baseSnapshot,
        );
        if (merged !== null) {
          if (fieldMapping.zoteroField === "tags") {
            patchData.tags = notionTagsToZotero(merged);
          } else if (fieldMapping.zoteroField === "collections") {
            patchData.collections = merged;
          }
        }
      } else if (fieldMapping.mergeStrategy === MergeStrategy.SCALAR) {
        const newValue = await this._mergeScalarField(
          fieldMapping, notionValue, groupId, itemKey, baseSnapshot,
        );
        if (newValue !== null) {
          patchData[fieldMapping.zoteroField] = newValue;
        }
      }
    }

    let version = await ZoteroItemBridge.getItemVersion(groupId, itemKey);

    if (Object.keys(patchData).length > 0) {
      NRSLog.info(`Patching group item ${itemKey} with fields: ${Object.keys(patchData).join(", ")}`);
      version = await ZoteroItemBridge.patchItem(groupId, itemKey, patchData);
    }

    // Store new snapshot
    this._store.upsertSyncState(notionPageId, {
      zoteroItemKey: itemKey,
      zoteroGroupId: groupId,
      lastZoteroVersion: version,
      propertySnapshot: this._buildSnapshot(notionProps),
      lastSyncedAt: new Date().toISOString(),
      deleted: false,
    });
  }

  async _mergeArrayField(fieldMapping, notionValue, groupId, itemKey, baseSnapshot) {
    const notionCurrent = notionValue || [];
    const base = baseSnapshot[fieldMapping.notionName] || [];

    if (fieldMapping.zoteroField === "tags") {
      const zoteroCurrent = await ZoteroItemBridge.getItemTags(groupId, itemKey);
      const preserve = new Set([NOTERO_TAG]);
      const merged = threeWayMerge(base, notionCurrent, zoteroCurrent, preserve);
      if (JSON.stringify([...new Set(merged)].sort()) !== JSON.stringify([...new Set(zoteroCurrent)].sort())) {
        return merged;
      }
      return null;
    }

    if (fieldMapping.zoteroField === "collections") {
      const zoteroCurrentKeys = await ZoteroItemBridge.getItemCollectionKeys(groupId, itemKey);
      const notionKeys = this._collections.namesToKeys(groupId, notionCurrent);
      const baseKeys = this._collections.namesToKeys(groupId, base);
      const merged = threeWayMerge(baseKeys, notionKeys, zoteroCurrentKeys);
      if (JSON.stringify([...new Set(merged)].sort()) !== JSON.stringify([...new Set(zoteroCurrentKeys)].sort())) {
        return merged;
      }
      return null;
    }

    return null;
  }

  async _mergeScalarField(fieldMapping, notionValue, groupId, itemKey, baseSnapshot) {
    const notionCurrent = notionValue || "";
    const base = baseSnapshot[fieldMapping.notionName] || "";
    const zoteroCurrent = await ZoteroItemBridge.getItemField(groupId, itemKey, fieldMapping.zoteroField);

    const notionChanged = notionCurrent !== base;
    const zoteroChanged = zoteroCurrent !== base;

    if (!notionChanged) return null;
    if (notionChanged && !zoteroChanged) return notionCurrent;

    // Both changed - Zotero wins (conservative)
    NRSLog.warn(`Conflict on field '${fieldMapping.zoteroField}': both sides changed. Zotero wins.`);
    return null;
  }

  _buildSnapshot(notionProps) {
    const snapshot = {};
    for (const notionName of Object.keys(FIELD_MAP_BY_NOTION)) {
      if (notionName in notionProps) {
        snapshot[notionName] = notionProps[notionName];
      }
    }
    return snapshot;
  }
}
