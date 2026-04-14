#!/usr/bin/env bash
# ============================================================
# cleanup.sh — Remove everything installed by setup.sh
#
# Since everything is local to this directory, cleanup is
# simply deleting the local folders. Nothing was installed
# system-wide (except ffmpeg, which is asked about separately).
# ============================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
step()    { echo -e "\n${RED}▶ $*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

confirm() {
    read -rp "$1 [y/N] " ans
    [[ "${ans,,}" == "y" ]]
}

step "Video Documentation Cleanup"
echo "Removes all local installs. Nothing touches your system Python or global packages."
echo "---------------------------------------------------------------"

# ── Stop local ollama if running ─────────────────────────────────────────────
step "Stopping local ollama process"
OLLAMA_BIN="$SCRIPT_DIR/bin/ollama"
if pgrep -f "$OLLAMA_BIN serve" &>/dev/null; then
    pkill -f "$OLLAMA_BIN serve" && info "ollama stopped"
else
    info "ollama not running"
fi
rm -f "$SCRIPT_DIR/ollama.sock"

# ── Remove local directories ──────────────────────────────────────────────────
for dir_name in "venv" "bin" "models"; do
    target="$SCRIPT_DIR/$dir_name"
    step "Removing ./$dir_name"
    if [[ -d "$target" ]]; then
        SIZE=$(du -sh "$target" 2>/dev/null | cut -f1)
        if confirm "  Remove $target ($SIZE)?"; then
            rm -rf "$target" && info "Removed $target"
        else
            warn "Skipped $target"
        fi
    else
        info "$target not found, skipping"
    fi
done

# ── Remove generated docs ─────────────────────────────────────────────────────
step "Generated documentation (./video_docs)"
DOC_DIR="$SCRIPT_DIR/video_docs"
if [[ -d "$DOC_DIR" ]]; then
    SIZE=$(du -sh "$DOC_DIR" 2>/dev/null | cut -f1)
    if confirm "  Remove $DOC_DIR ($SIZE)?"; then
        rm -rf "$DOC_DIR" && info "Removed $DOC_DIR"
    else
        warn "Kept $DOC_DIR"
    fi
else
    info "No ./video_docs found"
fi

# ── run.sh ────────────────────────────────────────────────────────────────────
step "Removing ./run.sh"
if [[ -f "$SCRIPT_DIR/run.sh" ]]; then
    rm -f "$SCRIPT_DIR/run.sh" && info "Removed run.sh"
else
    info "run.sh not found"
fi

# ── ffmpeg (optional — may have been pre-installed) ───────────────────────────
step "ffmpeg (system package)"
if command -v ffmpeg &>/dev/null; then
    if confirm "  Remove ffmpeg via apt? (only if setup.sh installed it)"; then
        sudo apt-get remove -y ffmpeg && info "ffmpeg removed"
    else
        warn "Kept ffmpeg"
    fi
else
    info "ffmpeg not installed"
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Cleanup complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "To also remove the scripts themselves:"
echo "  rm -f setup.sh process_videos.py cleanup.sh"
