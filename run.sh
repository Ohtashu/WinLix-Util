#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  Linux Toolkit — one-command launcher
#  Usage:  ./run.sh
#
#  Uses a venv to bypass PEP 668 "externally managed" restrictions.
# ─────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# ── Find python3 ─────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    exit 1
fi

# ── Create venv if missing or broken ─────────────────────
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment…"
    "$PYTHON" -m venv "$VENV_DIR"
fi

# ── Install the toolkit (editable) if not already ────────
if ! "$VENV_DIR/bin/python" -c "import toolkit" &>/dev/null; then
    echo "Installing dependencies…"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip -q 2>/dev/null
    "$VENV_DIR/bin/python" -m pip install -e "$SCRIPT_DIR" -q 2>/dev/null
fi

# ── Launch ───────────────────────────────────────────────
exec "$VENV_DIR/bin/python" -m toolkit "$@"
