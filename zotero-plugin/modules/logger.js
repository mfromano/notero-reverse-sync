/* global Zotero */
var NRSLog = {
  _prefix: "[NoteroReverseSync]",

  info(msg, ...args) {
    Zotero.debug(`${this._prefix} INFO: ${msg}` + (args.length ? " " + JSON.stringify(args) : ""));
  },

  warn(msg, ...args) {
    Zotero.debug(`${this._prefix} WARN: ${msg}` + (args.length ? " " + JSON.stringify(args) : ""));
  },

  error(msg, ...args) {
    Zotero.debug(`${this._prefix} ERROR: ${msg}` + (args.length ? " " + JSON.stringify(args) : ""), 1);
  },

  debug(msg, ...args) {
    Zotero.debug(`${this._prefix} DEBUG: ${msg}` + (args.length ? " " + JSON.stringify(args) : ""), 5);
  },
};
