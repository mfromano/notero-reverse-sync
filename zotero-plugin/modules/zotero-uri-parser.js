/* Parse Zotero URIs into their components. */

var _ZOTERO_URI_RE = /https?:\/\/(?:www\.)?zotero\.org\/(users|groups)\/(\d+)\/items\/([A-Z0-9]+)/;
var _ZOTERO_USER_SLUG_RE = /https?:\/\/(?:www\.)?zotero\.org\/([a-zA-Z][a-zA-Z0-9_-]*)\/items\/([A-Z0-9]+)/;

/**
 * Parse a Zotero URI into its components.
 *
 * Accepts URIs like:
 *   https://www.zotero.org/groups/483726/items/A5X7AKTH
 *   https://zotero.org/users/12345/items/ABCD1234
 *   https://zotero.org/mfromano/items/WFHVZPHT  (personal library by username)
 *
 * Returns { libraryType, libraryId, itemKey } or null.
 */
function parseZoteroUri(uri) {
  let m = _ZOTERO_URI_RE.exec(uri);
  if (m) {
    return {
      libraryType: m[1],
      libraryId: parseInt(m[2], 10),
      itemKey: m[3],
    };
  }

  m = _ZOTERO_USER_SLUG_RE.exec(uri);
  if (m) {
    return {
      libraryType: "users",
      libraryId: 0,
      itemKey: m[2],
    };
  }

  return null;
}
