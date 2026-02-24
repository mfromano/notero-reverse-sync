/* global Zotero */

/**
 * Initial population: copy relevant items from personal library to
 * a Zotero group library and upload local PDFs.
 * Port of bootstrap.py.
 */
class BootstrapRunner {
  constructor(stateStore, notionClient, collectionResolver) {
    this._store = stateStore;
    this._notion = notionClient;
    this._collections = collectionResolver;
  }

  async run(groupId, progressCallback) {
    NRSLog.info(`Starting bootstrap for group ${groupId}`);
    const pages = await this._notion.queryAllPages();
    NRSLog.info(`Found ${pages.length} pages`);

    let created = 0;
    let alreadyInGroup = 0;
    let attachments = 0;
    let skipped = 0;
    const total = pages.length;

    for (let i = 0; i < pages.length; i++) {
      const page = pages[i];
      const pageId = page.id;
      const properties = page.properties || {};
      const parsed = extractSyncableProperties(properties);

      if (progressCallback) {
        progressCallback({ current: i + 1, total, created, skipped });
      }

      // Relevance filter
      const relevant = parsed["Relevant?"];
      if (relevant !== "Yes" && relevant !== "Highly") {
        skipped++;
        continue;
      }

      const zoteroUri = parsed.zotero_uri;
      if (!zoteroUri) { skipped++; continue; }

      const ref = parseZoteroUri(zoteroUri);
      if (!ref) {
        NRSLog.warn(`Cannot parse Zotero URI '${zoteroUri}' on page ${pageId}`);
        skipped++;
        continue;
      }

      // Check if already bootstrapped
      const existing = this._store.getSyncState(pageId);
      if (existing) {
        NRSLog.debug(`Page ${pageId} already has sync state, skipping`);
        skipped++;
        continue;
      }

      // Get source item from personal library
      let sourceItem;
      try {
        sourceItem = await ZoteroItemBridge.getItemFromRef(ref);
      } catch (e) {
        NRSLog.warn(`Source item ${ref.itemKey} not found: ${e.message}`);
        skipped++;
        continue;
      }

      // Check if item already exists in group via owl:sameAs
      let groupItemKey = this._findGroupItemKey(sourceItem, groupId);
      let groupItem;

      if (groupItemKey) {
        try {
          groupItem = await ZoteroItemBridge.getGroupItem(groupId, groupItemKey);
          alreadyInGroup++;
        } catch (e) {
          // Stale relation
          groupItemKey = null;
        }
      }

      if (!groupItemKey) {
        // Copy to group library
        groupItem = await ZoteroItemBridge.copyItemToGroup(sourceItem, groupId);
        groupItemKey = groupItem.key;
        NRSLog.info(`Created item ${groupItemKey} in group ${groupId} from ${ref.itemKey}`);
        created++;
      }

      // Upload local PDF if available
      const filePath = parsed["File Path"];
      if (filePath) {
        try {
          const hasPDF = await ZoteroItemBridge.hasPDFAttachment(groupId, groupItemKey);
          if (!hasPDF) {
            // Check file exists
            const file = Zotero.File.pathToFile(filePath);
            if (file.exists()) {
              await ZoteroItemBridge.addFileAttachment(groupId, groupItemKey, filePath);
              NRSLog.info(`Uploaded PDF to group item ${groupItemKey}`);
              attachments++;
            } else {
              NRSLog.warn(`File not found: ${filePath}`);
            }
          }
        } catch (e) {
          NRSLog.warn(`Failed to attach PDF to ${groupItemKey}: ${e.message}`);
        }
      }

      // Build snapshot and save sync state
      const snapshot = {};
      for (const notionName of Object.keys(FIELD_MAP_BY_NOTION)) {
        if (notionName in parsed) {
          snapshot[notionName] = parsed[notionName];
        }
      }

      this._store.upsertSyncState(pageId, {
        zoteroItemKey: groupItemKey,
        zoteroGroupId: groupId,
        lastZoteroVersion: groupItem.version,
        propertySnapshot: snapshot,
        lastSyncedAt: new Date().toISOString(),
        deleted: false,
      });
    }

    // Refresh collection cache
    this._collections.ensureCache(groupId);

    await this._store.save();

    const summary = `Bootstrap complete: ${created} items created, ${alreadyInGroup} already in group, ${attachments} PDFs attached, ${skipped} skipped`;
    NRSLog.info(summary);
    return { created, alreadyInGroup, attachments, skipped, summary };
  }

  /**
   * Check if an item has an owl:sameAs relation pointing to the target group.
   */
  _findGroupItemKey(item, groupId) {
    const relations = item.getRelations();
    const sameAs = relations["owl:sameAs"] || [];
    const uris = Array.isArray(sameAs) ? sameAs : [sameAs];
    const pattern = new RegExp(`groups/${groupId}/items/([A-Z0-9]+)`);
    for (const uri of uris) {
      const m = pattern.exec(uri);
      if (m) return m[1];
    }
    return null;
  }
}
