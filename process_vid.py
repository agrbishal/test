#!/usr/bin/env python3
"""
Video Documentation Generator
Uses local AI (Whisper for transcription + Ollama/llama3 for analysis)
to generate structured documentation from video recordings.

Run via:  bash run.sh /path/to/videos/
Setup via: bash setup.sh   (one-time)
"""

import os
import sys
import json
import subprocess
import argparse
import textwrap
from pathlib import Path
from datetime import datetime


# ── Sanity check — must run inside the venv ──────────────────────────────────

def check_venv():
    script_dir = Path(__file__).parent.resolve()
    venv_python = script_dir / "venv" / "bin" / "python"
    running_python = Path(sys.executable).resolve()
    if running_python != venv_python.resolve():
        print("❌ Not running inside the project venv.")
        print(f"   Expected: {venv_python}")
        print(f"   Got:      {running_python}")
        print("\nPlease use:  bash run.sh /path/to/videos/")
        sys.exit(1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd, check=True, capture=False):
    kwargs = dict(check=check, text=True)
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return subprocess.run(cmd, **kwargs)


def ollama_host() -> str:
    """Return the OLLAMA_HOST env var (set by run.sh to local socket)."""
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


# ── Audio extraction ──────────────────────────────────────────────────────────

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


# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe(audio_path: Path, model_size: str = "base") -> str:
    import whisper
    print(f"    ↳ transcribing with whisper ({model_size}) …")
    # Whisper model cache goes into ./models/whisper inside the project
    script_dir = Path(__file__).parent.resolve()
    cache_dir = str(script_dir / "models" / "whisper")
    os.makedirs(cache_dir, exist_ok=True)
    model = whisper.load_model(model_size, download_root=cache_dir)
    result = model.transcribe(str(audio_path), fp16=False, verbose=False)
    return result["text"].strip()


# ── LLM analysis via local Ollama ─────────────────────────────────────────────

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
    print(f"    ↳ analysing with llama3 (via local ollama) …")

    host = ollama_host()
    client = ol.Client(host=host)

    prompt = ANALYSIS_PROMPT.format(transcript=transcript[:12000])
    response = client.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2},
    )
    raw = response["message"]["content"].strip()

    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"title": video_name, "raw_analysis": raw, "parse_error": True}


# ── Markdown report ───────────────────────────────────────────────────────────

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


# ── Index page ────────────────────────────────────────────────────────────────

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


# ── Main pipeline ─────────────────────────────────────────────────────────────

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
        doc_path  = out_dir / (vpath.stem + ".md")
        meta_path = out_dir / (vpath.stem + ".json")

        if skip_existing and doc_path.exists():
            print(f"    ↳ skipping (already processed)\n")
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                all_meta.append({"file": vpath.name, "meta": meta, "doc_file": doc_path.name})
            continue

        audio = extract_audio(vpath, audio_dir)
        transcript = transcribe(audio, whisper_model)
        (out_dir / (vpath.stem + "_transcript.txt")).write_text(transcript)

        meta = analyse(transcript, vpath.name)
        meta_path.write_text(json.dumps(meta, indent=2))

        md = render_markdown(vpath.name, meta, transcript)
        doc_path.write_text(md)

        all_meta.append({"file": vpath.name, "meta": meta, "doc_file": doc_path.name})
        print(f"    ✅ → {doc_path.name}\n")

    index_path = out_dir / "INDEX.md"
    index_path.write_text(render_index(all_meta))
    print(f"\n📄 Index written → {index_path}")
    print(f"📁 All docs in  → {out_dir}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    check_venv()

    parser = argparse.ArgumentParser(
        description="Generate documentation from video recordings using local AI.\n"
                    "Run via:  bash run.sh /path/to/videos/"
    )
    parser.add_argument("video_dir", help="Directory containing your video files")
    parser.add_argument(
        "--out", "-o", default="./video_docs",
        help="Output directory for documentation (default: ./video_docs)"
    )
    parser.add_argument(
        "--whisper-model", "-w", default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base). 'small' recommended for technical content."
    )
    parser.add_argument(
        "--skip-existing", "-s", action="store_true",
        help="Skip videos that already have documentation (resume interrupted runs)"
    )
    parser.add_argument(
        "--no-install", action="store_true",
        help="(Internal) set automatically by run.sh"
    )
    args = parser.parse_args()

    process_all(args.video_dir, args.out, args.whisper_model, args.skip_existing)
