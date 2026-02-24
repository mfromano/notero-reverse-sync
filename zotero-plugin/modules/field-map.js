/* Field mapping from Notion property names to Zotero item fields. */

var MergeStrategy = {
  THREE_WAY: "three_way",
  SCALAR: "scalar",
  NO_SYNC: "no_sync",
};

var SYNCABLE_FIELDS = [
  { notionName: "Tags", zoteroField: "tags", mergeStrategy: MergeStrategy.THREE_WAY },
  { notionName: "Collections", zoteroField: "collections", mergeStrategy: MergeStrategy.THREE_WAY },
  { notionName: "Abstract", zoteroField: "abstractNote", mergeStrategy: MergeStrategy.SCALAR },
  { notionName: "Short Title", zoteroField: "shortTitle", mergeStrategy: MergeStrategy.SCALAR },
  { notionName: "Extra", zoteroField: "extra", mergeStrategy: MergeStrategy.SCALAR },
];

var FIELD_MAP_BY_NOTION = {};
for (const f of SYNCABLE_FIELDS) {
  FIELD_MAP_BY_NOTION[f.notionName] = f;
}

var NOTERO_TAG = "notion";

function notionTagsToZotero(tags) {
  return tags.map((t) => ({ tag: t }));
}

function zoteroTagsToList(tags) {
  return tags.map((t) => t.tag);
}
