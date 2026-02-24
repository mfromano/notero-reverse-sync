/* global Services, Zotero */

/**
 * Main plugin orchestrator.
 * Loaded by bootstrap.js, manages all sub-modules.
 */
class NoteroReverseSyncMain {
  constructor() {
    this._rootURI = null;
    this._scheduler = null;
    this._stateStore = null;
    this._notionClient = null;
    this._syncEngine = null;
    this._noteSyncEngine = null;
    this._collectionResolver = null;
    this._bootstrapRunner = null;
    this._menuItems = [];
  }

  async startup({ id, version, rootURI }) {
    this._rootURI = rootURI;

    // Load sub-modules (order matters - dependencies first)
    const modules = [
      "logger",
      "field-map",
      "tag-merger",
      "zotero-uri-parser",
      "notion-property-parser",
      "notion-block-parser",
      "sync-state-store",
      "notion-client",
      "zotero-item-bridge",
      "collection-resolver",
      "sync-engine",
      "note-sync-engine",
      "bootstrap-runner",
      "polling-scheduler",
    ];
    for (const mod of modules) {
      Services.scriptloader.loadSubScript(rootURI + `modules/${mod}.js`);
    }

    // Initialize components
    this._stateStore = new SyncStateStore();
    await this._stateStore.load();

    this._notionClient = new NotionAPIClient();
    this._collectionResolver = new CollectionResolver(this._stateStore);

    this._syncEngine = new PropertySyncEngine(
      this._stateStore,
      this._notionClient,
      this._collectionResolver,
    );

    const deleteOrphaned =
      Zotero.Prefs.get("extensions.notero-reverse-sync.deleteOrphanedNotes", true) || false;
    this._noteSyncEngine = new NoteSyncEngine(
      this._stateStore,
      this._notionClient,
      deleteOrphaned,
    );

    this._bootstrapRunner = new BootstrapRunner(
      this._stateStore,
      this._notionClient,
      this._collectionResolver,
    );

    // Start polling (preference pane is registered in bootstrap.js)
    this._scheduler = new PollingScheduler(
      this._syncEngine,
      this._noteSyncEngine,
      this._notionClient,
      this._stateStore,
    );
    this._scheduler.start();

    NRSLog.info(`Notero Reverse Sync v${version} started`);
  }

  shutdown(reason) {
    if (this._scheduler) {
      this._scheduler.stop();
    }
    if (this._stateStore) {
      this._stateStore.saveSync();
    }
    NRSLog.info("Notero Reverse Sync shut down");
  }

  onMainWindowLoad(window) {
    const doc = window.document;

    // Add menu items under Tools
    const menuPopup = doc.getElementById("menu_ToolsPopup");
    if (!menuPopup) return;

    // Separator
    const sep = doc.createXULElement("menuseparator");
    sep.id = "notero-rs-separator";
    menuPopup.appendChild(sep);
    this._menuItems.push(sep);

    // Sync Now
    const syncItem = doc.createXULElement("menuitem");
    syncItem.id = "notero-rs-sync-now";
    syncItem.setAttribute("label", "Notero Reverse Sync: Sync Now");
    syncItem.addEventListener("command", () => this._onSyncNow());
    menuPopup.appendChild(syncItem);
    this._menuItems.push(syncItem);

    // Bootstrap
    const bootstrapItem = doc.createXULElement("menuitem");
    bootstrapItem.id = "notero-rs-bootstrap";
    bootstrapItem.setAttribute("label", "Notero Reverse Sync: Run Bootstrap");
    bootstrapItem.addEventListener("command", () => this._onBootstrap());
    menuPopup.appendChild(bootstrapItem);
    this._menuItems.push(bootstrapItem);
  }

  onMainWindowUnload(window) {
    for (const item of this._menuItems) {
      item.remove();
    }
    this._menuItems = [];
  }

  async _onSyncNow() {
    NRSLog.info("Manual sync triggered");
    try {
      await this._scheduler.poll();
      // Show a brief notification
      const ps = Services.prompt;
      ps.alert(null, "Notero Reverse Sync", "Sync complete.");
    } catch (e) {
      NRSLog.error(`Manual sync failed: ${e.message}`);
      Services.prompt.alert(null, "Notero Reverse Sync", `Sync failed: ${e.message}`);
    }
  }

  async _onBootstrap() {
    const groupId =
      Zotero.Prefs.get("extensions.notero-reverse-sync.zoteroGroupId", true) || 0;

    if (!groupId) {
      Services.prompt.alert(
        null,
        "Notero Reverse Sync",
        "Please set a Zotero Group ID in preferences first.",
      );
      return;
    }

    NRSLog.info("Manual bootstrap triggered");
    try {
      const result = await this._bootstrapRunner.run(groupId);
      Services.prompt.alert(null, "Notero Reverse Sync", result.summary);
    } catch (e) {
      NRSLog.error(`Bootstrap failed: ${e.message}`);
      Services.prompt.alert(null, "Notero Reverse Sync", `Bootstrap failed: ${e.message}`);
    }
  }
}
