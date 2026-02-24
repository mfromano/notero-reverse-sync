#!/bin/bash
# Build the Zotero plugin as an .xpi file
set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="$PLUGIN_DIR/notero-reverse-sync.xpi"

# Remove old build
rm -f "$OUTPUT"

# Create xpi (which is just a zip)
cd "$PLUGIN_DIR"
zip -r "$OUTPUT" \
  manifest.json \
  bootstrap.js \
  prefs.js \
  content/ \
  locale/ \
  modules/ \
  icons/ \
  -x "*.DS_Store" -x "build.sh" -x "*.xpi" -x "update.json"

echo "Built: $OUTPUT"
echo ""
echo "To install:"
echo "  1. Open Zotero"
echo "  2. Tools > Add-ons"
echo "  3. Gear icon > Install Add-on From File..."
echo "  4. Select $OUTPUT"
