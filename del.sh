#!/usr/bin/env env bash
# ============================================================
# cleanup.sh — Remove everything installed by process_videos.py
# ============================================================
# What this removes:
#   1. Python packages: openai-whisper, ollama, tqdm (and deps)
#   2. Ollama binary + models
#   3. ffmpeg (if you want — prompted)
#   4. Whisper model cache (~/.cache/whisper)
#   5. Ollama model cache (~/.ollama)
#   6. Optionally: the generated ./video_docs output folder
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
heading() { echo -e "\n${RED}▶ $*${NC}"; }

confirm() {
    read -rp "$1 [y/N] " ans
    [[ "${ans,,}" == "y" ]]
}

heading "Video Documentation Cleanup Script"
echo "This will remove packages and data installed by process_videos.py"
echo "---------------------------------------------------------------"

# ── 1. Stop ollama service ───────────────────────────────────────────────────
heading "Stopping ollama service"
if pgrep -x ollama &>/dev/null; then
    pkill -x ollama && info "ollama service stopped" || warn "Could not stop ollama"
else
    info "ollama service not running"
fi

# ── 2. Remove Python packages ────────────────────────────────────────────────
heading "Removing Python packages"
PKGS=("openai-whisper" "ollama" "tqdm" "torch" "torchvision" "torchaudio"
      "numpy" "more-itertools" "tiktoken" "regex" "ffmpeg-python")

for pkg in "${PKGS[@]}"; do
    if pip show "$pkg" &>/dev/null 2>&1; then
        pip uninstall -y "$pkg" && info "Removed $pkg" || warn "Could not remove $pkg"
    else
        echo "  – $pkg not installed, skipping"
    fi
done

# ── 3. Remove ollama binary ──────────────────────────────────────────────────
heading "Removing ollama binary"
OLLAMA_BIN=$(which ollama 2>/dev/null || true)
if [[ -n "$OLLAMA_BIN" ]]; then
    sudo rm -f "$OLLAMA_BIN" && info "Removed $OLLAMA_BIN"
else
    info "ollama binary not found"
fi
# Common install locations
for loc in /usr/local/bin/ollama /usr/bin/ollama; do
    [[ -f "$loc" ]] && sudo rm -f "$loc" && info "Removed $loc"
done

# ── 4. Remove ollama system service (if installed) ───────────────────────────
heading "Removing ollama systemd service"
if systemctl list-unit-files ollama.service &>/dev/null 2>&1; then
    sudo systemctl stop ollama  2>/dev/null || true
    sudo systemctl disable ollama 2>/dev/null || true
    sudo rm -f /etc/systemd/system/ollama.service
    sudo systemctl daemon-reload
    info "Removed ollama systemd service"
else
    info "No ollama systemd service found"
fi

# ── 5. Remove ollama model cache ─────────────────────────────────────────────
heading "Removing ollama model cache"
OLLAMA_DIR="${HOME}/.ollama"
if [[ -d "$OLLAMA_DIR" ]]; then
    SIZE=$(du -sh "$OLLAMA_DIR" 2>/dev/null | cut -f1)
    if confirm "  Remove ${OLLAMA_DIR} (${SIZE})? This deletes all downloaded LLM models."; then
        rm -rf "$OLLAMA_DIR" && info "Removed $OLLAMA_DIR"
    else
        warn "Skipped $OLLAMA_DIR"
    fi
else
    info "No ollama cache found at $OLLAMA_DIR"
fi

# ── 6. Remove Whisper model cache ────────────────────────────────────────────
heading "Removing Whisper model cache"
WHISPER_CACHE="${HOME}/.cache/whisper"
if [[ -d "$WHISPER_CACHE" ]]; then
    SIZE=$(du -sh "$WHISPER_CACHE" 2>/dev/null | cut -f1)
    if confirm "  Remove ${WHISPER_CACHE} (${SIZE})? This deletes all downloaded Whisper models."; then
        rm -rf "$WHISPER_CACHE" && info "Removed $WHISPER_CACHE"
    else
        warn "Skipped $WHISPER_CACHE"
    fi
else
    info "No Whisper cache found at $WHISPER_CACHE"
fi

# ── 7. ffmpeg (optional — it may have been pre-installed) ────────────────────
heading "ffmpeg"
if command -v ffmpeg &>/dev/null; then
    if confirm "  Remove ffmpeg? (only do this if it was installed by process_videos.py)"; then
        sudo apt-get remove -y ffmpeg && info "Removed ffmpeg"
    else
        warn "Kept ffmpeg"
    fi
else
    info "ffmpeg not installed"
fi

# ── 8. Remove generated output directory ─────────────────────────────────────
heading "Generated documentation"
DOC_DIR="./video_docs"
if [[ -d "$DOC_DIR" ]]; then
    SIZE=$(du -sh "$DOC_DIR" 2>/dev/null | cut -f1)
    if confirm "  Remove generated docs at ${DOC_DIR} (${SIZE})?"; then
        rm -rf "$DOC_DIR" && info "Removed $DOC_DIR"
    else
        warn "Kept $DOC_DIR"
    fi
else
    info "No ./video_docs directory found"
fi

# ── 9. pip cache (optional) ───────────────────────────────────────────────────
heading "pip cache"
if confirm "  Clear pip cache to free disk space?"; then
    pip cache purge && info "pip cache cleared"
else
    warn "Kept pip cache"
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Cleanup complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "If you also want to remove the scripts themselves:"
echo "  rm -f process_videos.py cleanup.sh"
