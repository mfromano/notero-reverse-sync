/* global Services, ChromeUtils */
var NoteroReverseSync;

function install(data, reason) {}

function uninstall(data, reason) {}

async function startup({ id, version, rootURI }) {
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
