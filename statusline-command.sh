#!/usr/bin/env bash
# Claude Code status line — macOS/Linux wrapper.
# Pipes Claude Code's status-line JSON (stdin) to the cross-platform Python core
# living next to this file. Keeping the logic in statusline.py means macOS, Linux
# and Windows all share one implementation. Requires python3.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python)"
exec "$PY" "$DIR/statusline.py"
