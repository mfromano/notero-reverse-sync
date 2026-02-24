/**
 * Three-way merge for array fields (tags, collections).
 *
 * base:           snapshot from last sync (common ancestor)
 * notionCurrent:  current values in Notion
 * zoteroCurrent:  current values in Zotero
 * preserve:       Set of values that must always be in the result
 *
 * Returns merged array.
 */
function threeWayMerge(base, notionCurrent, zoteroCurrent, preserve) {
  const baseSet = new Set(base);
  const notionSet = new Set(notionCurrent);
  const zoteroSet = new Set(zoteroCurrent);

  // What Notion did since base
  const notionAdded = new Set([...notionSet].filter((x) => !baseSet.has(x)));
  const notionRemoved = new Set([...baseSet].filter((x) => !notionSet.has(x)));

  // Start from Zotero's current state and apply Notion's changes
  const result = new Set(zoteroSet);
  for (const item of notionAdded) result.add(item);
  for (const item of notionRemoved) result.delete(item);

  // Always preserve certain values
  if (preserve) {
    for (const item of preserve) result.add(item);
  }

  // Maintain stable order: Zotero's order first, then new additions sorted
  const ordered = zoteroCurrent.filter((v) => result.has(v));
  const newItems = [...result].filter((v) => !ordered.includes(v)).sort();
  return [...ordered, ...newItems];
}
