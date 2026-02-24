/* global Zotero */

/**
 * Note content sync: Notion blocks -> Zotero child notes.
 * Port of sync/note_sync.py.
 */

var ZOTERO_NOTES_HEADING = "Zotero Notes";

class NoteSyncEngine {
  constructor(stateStore, notionClient, deleteOrphaned = false) {
    this._store = stateStore;
    this._notion = notionClient;
    this._deleteOrphaned = deleteOrphaned;
  }

  async syncPageNotes(notionPageId, groupId, parentItemKey) {
    // 1. Fetch all top-level blocks of the page
    const blocks = await this._notion.getBlockChildren(notionPageId);

    // 2. Find the "Zotero Notes" heading and collect blocks under it
    const noteSections = this._extractNoteSections(blocks);
    if (!noteSections.length) {
      NRSLog.debug(`No '${ZOTERO_NOTES_HEADING}' heading found on page ${notionPageId}`);
      return;
    }

    // 3. Get existing note sync states for this parent
    const existingStates = this._store.getNoteSyncStatesForParent(parentItemKey, groupId);
    const trackedBlockIds = {};
    for (const s of existingStates) {
      trackedBlockIds[s.notionBlockId] = s;
    }

    // 4. Process each note section
    for (const section of noteSections) {
      const blockId = section.blockId;
      const childBlocks = section.blocks;
      if (!childBlocks.length) continue;

      const contentHash = computeBlocksHash(childBlocks);

      if (trackedBlockIds[blockId]) {
        // Existing tracked note
        const state = trackedBlockIds[blockId];
        delete trackedBlockIds[blockId];

        if (contentHash !== state.contentHash) {
          await this._updateExistingNote(state.zoteroNoteKey, groupId, childBlocks, blockId, contentHash, parentItemKey);
        } else {
          NRSLog.debug(`Note block ${blockId} unchanged, skipping`);
        }
      } else {
        // New note block
        await this._createNewNote(groupId, parentItemKey, childBlocks, blockId, contentHash);
      }
    }

    // 5. Handle orphaned notes
    for (const [blockId, state] of Object.entries(trackedBlockIds)) {
      if (this._deleteOrphaned) {
        NRSLog.info(`Deleting orphaned Zotero note ${state.zoteroNoteKey}`);
        await ZoteroItemBridge.deleteNote(groupId, state.zoteroNoteKey);
        this._store.deleteNoteSyncState(blockId);
      } else {
        NRSLog.info(`Orphaned note block ${blockId} (Zotero key ${state.zoteroNoteKey}) -- skipping deletion`);
      }
    }
  }

  _extractNoteSections(blocks) {
    const sections = [];
    let inNotesSection = false;

    for (const block of blocks) {
      const bt = block.type || "";

      if (bt === "heading_1" || bt === "heading_2" || bt === "heading_3") {
        const text = this._getBlockText(block);
        if (text.trim() === ZOTERO_NOTES_HEADING) {
          inNotesSection = true;
          continue;
        } else if (inNotesSection) {
          break;
        }
      }

      if (inNotesSection) {
        if (block.has_children) {
          sections.push({
            blockId: block.id,
            blocks: block.children || [block],
          });
        } else {
          sections.push({
            blockId: block.id,
            blocks: [block],
          });
        }
      }
    }

    return sections;
  }

  _getBlockText(block) {
    const bt = block.type || "";
    const blockData = block[bt] || {};
    const richText = blockData.rich_text || [];
    return richText.map((rt) => rt.plain_text || "").join("");
  }

  async _updateExistingNote(zoteroNoteKey, groupId, blocks, blockId, contentHash, parentItemKey) {
    const html = blocksToHtml(blocks);
    NRSLog.info(`Updating Zotero note ${zoteroNoteKey} from Notion block ${blockId}`);

    try {
      await ZoteroItemBridge.updateNote(groupId, zoteroNoteKey, html);
      this._store.upsertNoteSyncState(blockId, {
        zoteroNoteKey,
        zoteroParentKey: parentItemKey,
        zoteroGroupId: groupId,
        contentHash,
        lastSyncedAt: new Date().toISOString(),
      });
    } catch (e) {
      NRSLog.error(`Failed to update note ${zoteroNoteKey}: ${e.message}`);
    }
  }

  async _createNewNote(groupId, parentItemKey, blocks, blockId, contentHash) {
    const html = blocksToHtml(blocks);
    NRSLog.info(`Creating new Zotero note from Notion block ${blockId}`);

    try {
      const result = await ZoteroItemBridge.createNote(groupId, parentItemKey, html);
      this._store.upsertNoteSyncState(blockId, {
        zoteroNoteKey: result.key,
        zoteroParentKey: parentItemKey,
        zoteroGroupId: groupId,
        contentHash,
        lastSyncedAt: new Date().toISOString(),
      });
    } catch (e) {
      NRSLog.error(`Failed to create note from block ${blockId}: ${e.message}`);
    }
  }
}
