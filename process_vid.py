#!/usr/bin/env python3
"""
Video Documentation Generator
Uses local AI (Whisper for transcription + Ollama/llama3 for analysis)
to generate structured documentation from video recordings.

Requirements installed automatically:
  - openai-whisper  (local speech-to-text)
  - ollama          (local LLM runner — pulls llama3 model)
  - ffmpeg          (system package for audio extraction)
"""

import os
import sys
import json
import subprocess
import argparse
import textwrap
from pathlib import Path
from datetime import datetime

# ── Dependency bootstrap ────────────────────────────────────────────────────

def run(cmd, check=True, capture=False):
    kwargs = dict(check=check, text=True)
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return subprocess.run(cmd, **kwargs)

def ensure_deps():
    print("📦 Checking / installing dependencies …")

    # ffmpeg (system)
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        print("  Installing ffmpeg …")
        run(["sudo", "apt-get", "install", "-y", "ffmpeg"])
    else:
        print("  ✓ ffmpeg")

    # Python packages
    pkgs = {
        "whisper":  "openai-whisper",
        "ollama":   "ollama",
        "tqdm":     "tqdm",
    }
    for mod, pkg in pkgs.items():
        try:
            __import__(mod)
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  Installing {pkg} …")
            run([sys.executable, "-m", "pip", "install", "--quiet", pkg])

    # ollama binary
    if subprocess.run(["which", "ollama"], capture_output=True).returncode != 0:
        print("  Installing ollama binary …")
        run("curl -fsSL https://ollama.com/install.sh | sh", shell=True)
    else:
        print("  ✓ ollama binary")

    # Start ollama service (daemon)
    r = run(["pgrep", "-x", "ollama"], check=False, capture=True)
    if r.returncode != 0:
        print("  Starting ollama service …")
        subprocess.Popen(["ollama", "serve"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time; time.sleep(3)
    else:
        print("  ✓ ollama service running")

    # Pull model
    print("  Pulling llama3 model (first run may take a few minutes) …")
    run(["ollama", "pull", "llama3"])
    print("✅ All dependencies ready.\n")


# ── Audio extraction ────────────────────────────────────────────────────────

def extract_audio(video_path: Path, out_dir: Path) -> Path:
    audio_path = out_dir / (video_path.stem + ".wav")
    if audio_path.exists():
        print(f"    ↳ audio already extracted: {audio_path.name}")
        return audio_path
    print(f"    ↳ extracting audio …")
    run([
        "ffmpeg", "-y", "-i", str(video_path),
        "-ar", "16000", "-ac", "1", "-vn",
        str(audio_path)
    ], capture=True)
    return audio_path


# ── Transcription ───────────────────────────────────────────────────────────

def transcribe(audio_path: Path, model_size: str = "base") -> str:
    import whisper
    print(f"    ↳ transcribing with whisper ({model_size}) …")
    model = whisper.load_model(model_size)
    result = model.transcribe(str(audio_path), fp16=False, verbose=False)
    return result["text"].strip()


# ── LLM analysis via Ollama ─────────────────────────────────────────────────

ANALYSIS_PROMPT = """
You are a technical documentation assistant. Given the transcript of a video recording, produce a structured JSON document with exactly these fields:

{{
  "title": "A concise, descriptive title for the video (max 10 words)",
  "summary": "2-3 sentence executive summary of what was covered",
  "agenda": ["Agenda item 1", "Agenda item 2", "…"],
  "topics_covered": ["Topic A", "Topic B", "…"],
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "…"],
  "labels": ["label1", "label2", "…"],
  "estimated_duration_minutes": <integer>,
  "audience": "Who this recording is for",
  "difficulty_level": "Beginner | Intermediate | Advanced"
}}

Rules:
- Output ONLY valid JSON — no markdown fences, no preamble.
- agenda: ordered list of sections/topics discussed in sequence.
- topics_covered: flat list of concepts, technologies, or subject areas.
- labels: short snake_case tags useful for search/categorisation.
- If a field cannot be determined, use null.

TRANSCRIPT:
{transcript}
"""

def analyse(transcript: str, video_name: str) -> dict:
    import ollama as ol
    print(f"    ↳ analysing with llama3 …")
    prompt = ANALYSIS_PROMPT.format(transcript=transcript[:12000])  # ~3k tokens
    response = ol.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2},
    )
    raw = response["message"]["content"].strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: return raw text in a minimal dict
        return {"title": video_name, "raw_analysis": raw, "parse_error": True}


# ── Markdown report ─────────────────────────────────────────────────────────

def render_markdown(video_name: str, meta: dict, transcript: str) -> str:
    def ul(items):
        if not items:
            return "_None identified_"
        return "\n".join(f"- {i}" for i in items)

    agenda_md = ""
    if meta.get("agenda"):
        for idx, item in enumerate(meta["agenda"], 1):
            agenda_md += f"{idx}. {item}\n"
    else:
        agenda_md = "_Not identified_\n"

    return f"""# {meta.get('title', video_name)}

> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  
> **Source file:** `{video_name}`  
> **Audience:** {meta.get('audience', 'N/A')}  
> **Difficulty:** {meta.get('difficulty_level', 'N/A')}  
> **Est. duration:** {meta.get('estimated_duration_minutes', 'N/A')} min  
> **Labels:** {', '.join(f'`{l}`' for l in (meta.get('labels') or []))}

---

## Summary

{meta.get('summary', '_No summary generated._')}

---

## Agenda

{agenda_md}
---

## Topics Covered

{ul(meta.get('topics_covered'))}

---

## Key Takeaways

{ul(meta.get('key_takeaways'))}

---

## Full Transcript

<details>
<summary>Click to expand transcript</summary>

{textwrap.fill(transcript, width=100)}

</details>
"""


# ── Index page ──────────────────────────────────────────────────────────────

def render_index(all_meta: list) -> str:
    rows = ""
    for m in all_meta:
        title   = m['meta'].get('title', m['file'])
        labels  = ', '.join(f"`{l}`" for l in (m['meta'].get('labels') or []))
        summary = (m['meta'].get('summary') or '')[:120]
        rows += f"| [{title}]({m['doc_file']}) | {labels} | {summary}… |\n"

    return f"""# 📹 Video Documentation Index

> Auto-generated by `process_videos.py` on {datetime.now().strftime('%Y-%m-%d %H:%M')}  
> Total videos: **{len(all_meta)}**

| Video | Labels | Summary |
|-------|--------|---------|
{rows}
"""


# ── Main pipeline ───────────────────────────────────────────────────────────

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"}

def process_all(video_dir: str, out_dir: str, whisper_model: str, skip_existing: bool):
    video_dir = Path(video_dir).resolve()
    out_dir   = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = out_dir / "_audio"
    audio_dir.mkdir(exist_ok=True)

    videos = sorted([f for f in video_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS])
    if not videos:
        print(f"❌ No video files found in {video_dir}")
        sys.exit(1)

    print(f"🎬 Found {len(videos)} video(s) in {video_dir}\n")
    all_meta = []

    for i, vpath in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] {vpath.name}")
        doc_path = out_dir / (vpath.stem + ".md")
        meta_path = out_dir / (vpath.stem + ".json")

        if skip_existing and doc_path.exists():
            print(f"    ↳ skipping (already processed)\n")
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                all_meta.append({"file": vpath.name, "meta": meta, "doc_file": doc_path.name})
            continue

        # 1. Extract audio
        audio = extract_audio(vpath, audio_dir)

        # 2. Transcribe
        transcript = transcribe(audio, whisper_model)
        (out_dir / (vpath.stem + "_transcript.txt")).write_text(transcript)

        # 3. Analyse
        meta = analyse(transcript, vpath.name)
        meta_path.write_text(json.dumps(meta, indent=2))

        # 4. Write markdown doc
        md = render_markdown(vpath.name, meta, transcript)
        doc_path.write_text(md)

        all_meta.append({"file": vpath.name, "meta": meta, "doc_file": doc_path.name})
        print(f"    ✅ → {doc_path.name}\n")

    # Write index
    index_path = out_dir / "INDEX.md"
    index_path.write_text(render_index(all_meta))
    print(f"\n📄 Index written → {index_path}")
    print(f"📁 All docs in  → {out_dir}")


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate documentation from video recordings using local AI."
    )
    parser.add_argument(
        "video_dir",
        help="Directory containing your video files"
    )
    parser.add_argument(
        "--out", "-o",
        default="./video_docs",
        help="Output directory for documentation (default: ./video_docs)"
    )
    parser.add_argument(
        "--whisper-model", "-w",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base). Use 'small' or 'medium' for better accuracy."
    )
    parser.add_argument(
        "--skip-existing", "-s",
        action="store_true",
        help="Skip videos that already have documentation"
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip dependency installation (assume everything is already installed)"
    )
    args = parser.parse_args()

    if not args.no_install:
        ensure_deps()

    process_all(args.video_dir, args.out, args.whisper_model, args.skip_existing)
