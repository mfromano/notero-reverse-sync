/* global Zotero */

/**
 * Bridge between sync logic and Zotero's internal JavaScript API.
 * Replaces the REST API client from the Python version.
 */
class ZoteroItemBridge {
  /**
   * Get Zotero's internal libraryID from a group's numeric ID.
   */
  static getLibraryID(groupId) {
    return Zotero.Groups.getLibraryIDFromGroupID(groupId);
  }

  /**
   * Get the user's personal library ID.
   */
  static getUserLibraryID() {
    return Zotero.Libraries.userLibraryID;
  }

  /**
   * Resolve a parsed Zotero URI ref to a libraryID.
   * Handles users/0 (personal library) and groups/<id>.
   */
  static resolveLibraryID(ref) {
    if (ref.libraryType === "users") {
      return this.getUserLibraryID();
    }
    return this.getLibraryID(ref.libraryId);
  }

  /**
   * Get an item by key from a group library.
   */
  static async getGroupItem(groupId, itemKey) {
    const libraryID = this.getLibraryID(groupId);
    const item = await Zotero.Items.getByLibraryAndKeyAsync(libraryID, itemKey);
    if (!item) throw new Error(`Item not found: ${itemKey} in group ${groupId}`);
    return item;
  }

  /**
   * Get an item from the user's personal library by key.
   */
  static async getUserItem(itemKey) {
    const libraryID = this.getUserLibraryID();
    const item = await Zotero.Items.getByLibraryAndKeyAsync(libraryID, itemKey);
    if (!item) throw new Error(`Item not found: ${itemKey} in user library`);
    return item;
  }

  /**
   * Get an item from a parsed URI ref.
   */
  static async getItemFromRef(ref) {
    if (ref.libraryType === "users") {
      return this.getUserItem(ref.itemKey);
    }
    return this.getGroupItem(ref.libraryId, ref.itemKey);
  }

  /**
   * Copy an item from the user's personal library to a group library.
   * Returns the new item in the group.
   */
  static async copyItemToGroup(sourceItem, groupId) {
    const libraryID = this.getLibraryID(groupId);
    const newItem = sourceItem.clone(libraryID);
    // Clear collections (library-specific)
    newItem.setCollections([]);
    await newItem.saveTx();
    return newItem;
  }

  /**
   * Patch specific fields on an existing group item.
   */
  static async patchItem(groupId, itemKey, patchData) {
    const item = await this.getGroupItem(groupId, itemKey);

    for (const [field, value] of Object.entries(patchData)) {
      if (field === "tags") {
        // Replace all tags
        item.setTags(value.map((t) => (typeof t === "string" ? { tag: t } : t)));
      } else if (field === "collections") {
        // Convert collection keys to IDs
        const libraryID = item.libraryID;
        const colIDs = [];
        for (const key of value) {
          const col = Zotero.Collections.getByLibraryAndKey(libraryID, key);
          if (col) colIDs.push(col.id);
        }
        item.setCollections(colIDs);
      } else {
        item.setField(field, value);
      }
    }

    await item.saveTx();
    return item.version;
  }

  /**
   * Create a child note on a group item.
   */
  static async createNote(groupId, parentItemKey, noteHtml) {
    const libraryID = this.getLibraryID(groupId);
    const parentItem = await this.getGroupItem(groupId, parentItemKey);

    const note = new Zotero.Item("note");
    note.libraryID = libraryID;
    note.parentID = parentItem.id;
    note.setNote(noteHtml);
    await note.saveTx();

    return { key: note.key, version: note.version };
  }

  /**
   * Update an existing note's content.
   */
  static async updateNote(groupId, noteKey, noteHtml) {
    const note = await this.getGroupItem(groupId, noteKey);
    note.setNote(noteHtml);
    await note.saveTx();
    return note.version;
  }

  /**
   * Delete a note item.
   */
  static async deleteNote(groupId, noteKey) {
    try {
      const note = await this.getGroupItem(groupId, noteKey);
      await note.eraseTx();
    } catch (e) {
      NRSLog.warn(`Could not delete note ${noteKey}: ${e.message}`);
    }
  }

  /**
   * Get all collections for a group library.
   */
  static getCollections(groupId) {
    const libraryID = this.getLibraryID(groupId);
    const collections = Zotero.Collections.getByLibrary(libraryID);
    return collections.map((c) => ({ key: c.key, name: c.name }));
  }

  /**
   * Get tags on a group item as an array of strings.
   */
  static async getItemTags(groupId, itemKey) {
    const item = await this.getGroupItem(groupId, itemKey);
    return item.getTags().map((t) => t.tag);
  }

  /**
   * Get collection keys for a group item.
   */
  static async getItemCollectionKeys(groupId, itemKey) {
    const item = await this.getGroupItem(groupId, itemKey);
    const colIDs = item.getCollections();
    return colIDs
      .map((id) => {
        const col = Zotero.Collections.get(id);
        return col ? col.key : null;
      })
      .filter(Boolean);
  }

  /**
   * Get a scalar field value from a group item.
   */
  static async getItemField(groupId, itemKey, fieldName) {
    const item = await this.getGroupItem(groupId, itemKey);
    return item.getField(fieldName) || "";
  }

  /**
   * Get the version of a group item.
   */
  static async getItemVersion(groupId, itemKey) {
    const item = await this.getGroupItem(groupId, itemKey);
    return item.version;
  }

  /**
   * Add a linked-file PDF attachment to a group item from a local path.
   */
  static async addFileAttachment(groupId, parentItemKey, filePath) {
    const libraryID = this.getLibraryID(groupId);
    const parentItem = await this.getGroupItem(groupId, parentItemKey);

    const attachment = await Zotero.Attachments.importFromFile({
      file: filePath,
      libraryID: libraryID,
      parentItemID: parentItem.id,
      contentType: "application/pdf",
    });

    return attachment;
  }

  /**
   * Check if a group item already has a PDF attachment.
   */
  static async hasPDFAttachment(groupId, itemKey) {
    const item = await this.getGroupItem(groupId, itemKey);
    const attachmentIDs = item.getAttachments();
    for (const id of attachmentIDs) {
      const att = Zotero.Items.get(id);
      if (att && att.attachmentContentType === "application/pdf") {
        return true;
      }
    }
    return false;
  }
}
