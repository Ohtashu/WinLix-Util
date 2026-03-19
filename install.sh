#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  WinLix-Util — run without cloning
#
#  Linux / macOS:
#    curl -fsSL https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.sh | bash
#
#  Or with arguments:
#    curl -fsSL https://raw.githubusercontent.com/Ohtashu/WinLix-Util/main/install.sh | bash -s -- --help
#
#  Bypasses PEP 668 by using a dedicated venv.
#  Creates a global alias/symlink so the tool is available from anywhere.
# ─────────────────────────────────────────────────────────
set -euo pipefail

REPO="Ohtashu/WinLix-Util"
BRANCH="main"
INSTALL_DIR="${WINLIX_INSTALL_DIR:-$HOME/.winlix-util}"
VENV_DIR="$INSTALL_DIR/.venv"
BIN_LINK="$HOME/.local/bin/winlix-util"

echo "──────────────────────────────────────────"
echo "  WinLix-Util  —  remote launcher"
echo "──────────────────────────────────────────"

# ── Ensure python3 is available ──────────────────────────
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

# Verify version >= 3.10
PY_VER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10+ required (found $PY_VER)."
    exit 1
fi
echo "  Python: $PYTHON ($PY_VER)"

# ── Ensure python3-venv module is available ──────────────
if ! "$PYTHON" -m venv --help &>/dev/null; then
    echo "  python3-venv module not found. Attempting to install…"
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y "python${PY_VER}-venv" 2>/dev/null || sudo apt-get install -y python3-venv 2>/dev/null || true
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-libs 2>/dev/null || true
    elif command -v pacman &>/dev/null; then
        # Arch includes venv in python package — should already work
        true
    fi
    if ! "$PYTHON" -m venv --help &>/dev/null; then
        echo "ERROR: python3-venv is required but could not be installed."
        echo "       Install it manually: sudo apt install python3-venv  (Debian/Ubuntu)"
        exit 1
    fi
fi

# ── Download / update source ─────────────────────────────
if [ ! -f "$INSTALL_DIR/pyproject.toml" ]; then
    echo "  Downloading WinLix-Util…"
    mkdir -p "$INSTALL_DIR"
    if command -v curl &>/dev/null; then
        curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" \
            | tar xz --strip-components=1 -C "$INSTALL_DIR"
    elif command -v wget &>/dev/null; then
        wget -qO- "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" \
            | tar xz --strip-components=1 -C "$INSTALL_DIR"
    else
        echo "ERROR: curl or wget is required."
        exit 1
    fi
    echo "  ✔ Source downloaded."
else
    echo "  Source found at $INSTALL_DIR"
fi

# ── Create venv (PEP 668 safe — never touches system Python) ─
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "  Creating virtual environment…"
    "$PYTHON" -m venv "$VENV_DIR"
fi

# ── Install deps inside venv if needed ────────────────────
if ! "$VENV_DIR/bin/python" -c "import toolkit" &>/dev/null; then
    echo "  Installing dependencies…"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip -q 2>/dev/null
    "$VENV_DIR/bin/python" -m pip install -e "$INSTALL_DIR" -q 2>/dev/null
    echo "  ✔ Dependencies installed."
fi

# ── Create global symlink / wrapper ───────────────────────
mkdir -p "$(dirname "$BIN_LINK")"
cat > "$BIN_LINK" << 'WRAPPER'
#!/usr/bin/env bash
exec "$HOME/.winlix-util/.venv/bin/python" -m toolkit "$@"
WRAPPER
chmod +x "$BIN_LINK"

# Ensure ~/.local/bin is on PATH (hint for current session)
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo ""
    echo "  ℹ  Add ~/.local/bin to your PATH for global access:"
    echo "      export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo "      (Add this to your ~/.bashrc or ~/.zshrc)"
fi

echo ""
echo "  ✔ WinLix-Util installed. You can now run it from anywhere:"
echo "      winlix-util"
echo ""

# ── Launch ───────────────────────────────────────────────
exec "$VENV_DIR/bin/python" -m toolkit "$@"
