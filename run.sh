#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  Linux Toolkit — one-command launcher
#  Usage:  ./run.sh
# ─────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# ── Ensure python3 is available ──────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    exit 1
fi

# ── Create venv if missing or broken ─────────────────────
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment…"
    python3 -m venv "$VENV_DIR"
fi

# ── Install the toolkit (editable) if not already ────────
if ! "$VENV_DIR/bin/python" -c "import toolkit" &>/dev/null; then
    echo "Installing dependencies…"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR" -q
fi

# ── Launch ───────────────────────────────────────────────
exec "$VENV_DIR/bin/python" -m toolkit "$@"
