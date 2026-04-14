#!/usr/bin/env bash
# ============================================================
# setup.sh — One-time setup for video documentation pipeline
#
# Everything is installed LOCAL to this directory:
#   ./venv/          Python virtualenv + all packages
#   ./bin/           ollama binary (no system install)
#   ./models/        ollama model data (OLLAMA_MODELS)
#   ./run.sh         Convenience wrapper (use this to run)
# ============================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
step()    { echo -e "\n${GREEN}▶ $*${NC}"; }
die()     { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
BIN_DIR="$SCRIPT_DIR/bin"
MODELS_DIR="$SCRIPT_DIR/models"
OLLAMA_BIN="$BIN_DIR/ollama"
OLLAMA_SOCK="$SCRIPT_DIR/ollama.sock"

mkdir -p "$BIN_DIR" "$MODELS_DIR"

# ── Check Python ─────────────────────────────────────────────────────────────
step "Checking Python"
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null || die "Python not found")
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Found Python $PY_VER at $PYTHON"
[[ "${PY_VER/./}" -lt "38" ]] && die "Python 3.8+ required, found $PY_VER"

# ── ffmpeg (only system package needed — no root alternative viable) ──────────
step "Checking ffmpeg"
if ! command -v ffmpeg &>/dev/null; then
    warn "ffmpeg not found. Attempting install (requires sudo) …"
    sudo apt-get install -y ffmpeg && info "ffmpeg installed"
else
    info "ffmpeg already available: $(ffmpeg -version 2>&1 | head -1)"
fi

# ── Create virtualenv ─────────────────────────────────────────────────────────
step "Creating Python virtualenv at ./venv"
if [[ -d "$VENV_DIR" ]]; then
    info "venv already exists, skipping creation"
else
    "$PYTHON" -m venv "$VENV_DIR"
    info "venv created"
fi

# Activate
source "$VENV_DIR/bin/activate"
info "venv activated: $(which python)"

# Upgrade pip inside venv only
pip install --quiet --upgrade pip

# ── Install Python packages into venv ────────────────────────────────────────
step "Installing Python packages into venv"
pip install --quiet openai-whisper ollama tqdm
info "openai-whisper, ollama (client), tqdm installed"

# ── Install ollama binary locally ─────────────────────────────────────────────
step "Installing ollama binary locally to ./bin/ollama"
if [[ -f "$OLLAMA_BIN" ]]; then
    info "ollama binary already present"
else
    OS="linux"
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  ARCH_TAG="amd64" ;;
        aarch64) ARCH_TAG="arm64" ;;
        *)        die "Unsupported architecture: $ARCH" ;;
    esac

    OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-${OS}-${ARCH_TAG}"
    echo "  Downloading from $OLLAMA_URL …"
    curl -fsSL -o "$OLLAMA_BIN" "$OLLAMA_URL"
    chmod +x "$OLLAMA_BIN"
    info "ollama binary installed at $OLLAMA_BIN"
fi

# ── Pull llama3 model (stored locally in ./models) ────────────────────────────
step "Pulling llama3 model (stored in ./models — may take a few minutes)"

# Start a temporary local ollama server pointed at ./models
export OLLAMA_MODELS="$MODELS_DIR"
export OLLAMA_HOST="unix://$OLLAMA_SOCK"

# Kill any leftover
pkill -f "$OLLAMA_BIN serve" 2>/dev/null || true
rm -f "$OLLAMA_SOCK"

"$OLLAMA_BIN" serve &>/dev/null &
OLLAMA_PID=$!
echo "  ollama server PID: $OLLAMA_PID (temp, for model pull)"
sleep 4   # give it time to start

"$OLLAMA_BIN" pull llama3
info "llama3 model pulled → ./models"

# Stop temp server
kill "$OLLAMA_PID" 2>/dev/null || true
wait "$OLLAMA_PID" 2>/dev/null || true
rm -f "$OLLAMA_SOCK"

# ── Write run.sh convenience wrapper ─────────────────────────────────────────
step "Writing ./run.sh wrapper"
cat > "$SCRIPT_DIR/run.sh" << 'EOF'
#!/usr/bin/env bash
# run.sh — Start ollama (local) and run process_videos.py inside the venv
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_BIN="$SCRIPT_DIR/bin/ollama"
OLLAMA_SOCK="$SCRIPT_DIR/ollama.sock"
MODELS_DIR="$SCRIPT_DIR/models"

export OLLAMA_MODELS="$MODELS_DIR"
export OLLAMA_HOST="unix://$OLLAMA_SOCK"

# Start local ollama server if not already running
if ! pgrep -f "$OLLAMA_BIN serve" &>/dev/null; then
    echo "▶ Starting local ollama server …"
    "$OLLAMA_BIN" serve &>/dev/null &
    OLLAMA_PID=$!
    sleep 3
    echo "  ollama PID: $OLLAMA_PID"
fi

# Activate venv and run
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/process_videos.py" --no-install "$@"

# Stop ollama when done
echo "▶ Stopping local ollama server …"
pkill -f "$OLLAMA_BIN serve" 2>/dev/null || true
rm -f "$OLLAMA_SOCK"
EOF
chmod +x "$SCRIPT_DIR/run.sh"
info "run.sh created"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Everything is installed locally in this directory:"
echo "  ./venv/    — Python packages (whisper, ollama client, tqdm)"
echo "  ./bin/     — ollama binary"
echo "  ./models/  — llama3 model data"
echo ""
echo "To process your videos:"
echo ""
echo -e "  ${GREEN}bash run.sh /path/to/your/videos/${NC}"
echo ""
echo "Options:"
echo "  bash run.sh /path/to/videos/ --whisper-model small"
echo "  bash run.sh /path/to/videos/ --out ./my_docs --skip-existing"
echo ""
echo "To remove everything: bash cleanup.sh"
