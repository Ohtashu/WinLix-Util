#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  WinLix-Util — run without cloning
#
#  Linux / macOS:
#    curl -fsSL https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.sh | bash
#
#  Or with arguments:
#    curl -fsSL https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.sh | bash -s -- --help
# ─────────────────────────────────────────────────────────
set -euo pipefail

REPO="Ohtashu/WinLix-Util"
BRANCH="main"
INSTALL_DIR="${WINLIX_INSTALL_DIR:-$HOME/.winlix-util}"

echo "──────────────────────────────────────────"
echo "  WinLix-Util  —  remote launcher"
echo "──────────────────────────────────────────"

# ── Ensure python3 is available ──────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    exit 1
fi

# ── Download / update ────────────────────────────────────
if [ ! -f "$INSTALL_DIR/pyproject.toml" ]; then
    echo "Downloading WinLix-Util…"
    mkdir -p "$INSTALL_DIR"
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" \
        | tar xz --strip-components=1 -C "$INSTALL_DIR"
else
    echo "WinLix-Util already installed at $INSTALL_DIR"
    echo "  To update: rm -rf \"$INSTALL_DIR\" and re-run this script."
fi

# ── Create venv if missing ───────────────────────────────
VENV_DIR="$INSTALL_DIR/.venv"
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment…"
    python3 -m venv "$VENV_DIR"
fi

# ── Install deps if needed ───────────────────────────────
if ! "$VENV_DIR/bin/python" -c "import toolkit" &>/dev/null; then
    echo "Installing dependencies…"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -e "$INSTALL_DIR" -q
fi

# ── Launch ───────────────────────────────────────────────
echo ""
exec "$VENV_DIR/bin/python" -m toolkit "$@"
