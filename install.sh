#!/usr/bin/env bash
# One-shot installer for the Claude Code status line.
# Copies the script into ~/.claude/ and wires the statusLine block into
# ~/.claude/settings.json (preserving any existing settings).
#
# Usage:  ./install.sh
set -euo pipefail

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$CLAUDE_DIR/statusline-command.sh"
SETTINGS="$CLAUDE_DIR/settings.json"

command -v python3 >/dev/null 2>&1 || { echo "error: python3 is required" >&2; exit 1; }

mkdir -p "$CLAUDE_DIR"
cp "$SRC_DIR/statusline.py" "$CLAUDE_DIR/statusline.py"
cp "$SRC_DIR/statusline-command.sh" "$DEST"
chmod +x "$DEST"
echo "✓ installed statusline.py + wrapper -> $CLAUDE_DIR"

# Merge the statusLine block into settings.json without clobbering other keys.
python3 - "$SETTINGS" "$DEST" <<'PY'
import json, os, sys
settings_path, cmd = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            data = json.load(f) or {}
    except Exception:
        print(f"warning: {settings_path} is not valid JSON; leaving it untouched.")
        print("Add this block manually:")
        print(json.dumps({"statusLine": {"type": "command", "command": cmd, "padding": 0}}, indent=2))
        sys.exit(0)
data["statusLine"] = {"type": "command", "command": cmd, "padding": 0}
with open(settings_path, "w") as f:
    json.dump(data, f, indent=2)
print(f"✓ wired statusLine into {settings_path}")
PY

echo
echo "Done. Open a new Claude Code session (or wait for the next render) to see it."
