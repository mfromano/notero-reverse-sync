/* global Services, Zotero */
var NoteroReverseSync;

function install(data, reason) {}

function uninstall(data, reason) {}

async function startup({ id, version, rootURI }) {
  // Register preference pane FIRST, before anything else can fail
  Zotero.PreferencePanes.register({
    pluginID: "notero-reverse-sync@mfromano",
    src: rootURI + "content/preferences.xhtml",
    label: "Notero Reverse Sync",
    image: rootURI + "icons/icon-48.png",
  });

  Services.scriptloader.loadSubScript(rootURI + "modules/notero-reverse-sync.js");
  NoteroReverseSync = new NoteroReverseSyncMain();
  await NoteroReverseSync.startup({ id, version, rootURI });
}

function shutdown({ id, version, rootURI }, reason) {
  if (NoteroReverseSync) {
    NoteroReverseSync.shutdown(reason);
    NoteroReverseSync = null;
  }
}

function onMainWindowLoad({ window }) {
  if (NoteroReverseSync) {
    NoteroReverseSync.onMainWindowLoad(window);
  }
}

function onMainWindowUnload({ window }) {
  if (NoteroReverseSync) {
    NoteroReverseSync.onMainWindowUnload(window);
  }
}
