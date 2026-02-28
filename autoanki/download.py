"""Download video + Chinese subtitles from YouTube/Bilibili via yt-dlp."""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

PREFERRED_SUB_LANGS = [
    "zh-Hans", "zh", "zh-CN", "zh-Hant", "zh-TW",
    "zh-Hans-en", "zh-Hant-en",
    "en",
]


@dataclass
class DownloadResult:
    video_path: Path
    subtitle_path: Path
    title: str
    sub_lang: str  # language code of downloaded subs, e.g. "zh-Hans", "en"


def _extract_video_id(url: str) -> str | None:
    """Extract video ID from YouTube or Bilibili URL."""
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"(BV[A-Za-z0-9]+|av\d+)", url)
    if m:
        return m.group(1)
    return None


def _find_subtitle(output_dir: Path, video_id: str) -> tuple[Path, str] | None:
    """Find best subtitle file for a video ID. Returns (path, lang) or None."""
    for lang in PREFERRED_SUB_LANGS:
        candidate = output_dir / f"{video_id}.{lang}.vtt"
        if candidate.exists():
            return candidate, lang
    candidates = list(output_dir.glob(f"{video_id}*.vtt"))
    if candidates:
        path = candidates[0]
        lang = path.stem.split(".", 1)[-1] if "." in path.stem else "unknown"
        return path, lang
    return None


def download(url: str, output_dir: Path, cookies: str | None = None) -> DownloadResult:
    """Download video + Chinese subtitles from URL via yt-dlp."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing download
    video_id = _extract_video_id(url)
    if video_id:
        existing_video = output_dir / f"{video_id}.mp4"
        if existing_video.exists():
            sub = _find_subtitle(output_dir, video_id)
            if sub:
                meta_path = output_dir / f"{video_id}.info.json"
                title = json.loads(meta_path.read_text())["title"] if meta_path.exists() else video_id
                print(f"  Reusing existing download: {video_id}")
                return DownloadResult(existing_video, sub[0], title, sub[1])

    sub_langs = ",".join(PREFERRED_SUB_LANGS)
    output_template = str(output_dir / "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--js-runtimes", "node",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", sub_langs,
        "--sub-format", "vtt",
        "--convert-subs", "vtt",
        "--output", output_template,
        "--no-playlist",
        "--print-json",
        "--ignore-errors",
        "--sleep-requests", "1",
        "--write-info-json",
        url,
    ]

    if cookies:
        cmd.extend(["--cookies", cookies])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout.strip():
        meta = json.loads(result.stdout.strip().splitlines()[-1])
    else:
        raise RuntimeError(
            f"yt-dlp failed to download. stderr:\n{result.stderr}"
        )

    title = meta.get("title", "untitled")
    video_id = meta["id"]

    video_path = output_dir / f"{video_id}.mp4"
    if not video_path.exists():
        candidates = list(output_dir.glob(f"{video_id}*.mp4"))
        if candidates:
            video_path = candidates[0]
        else:
            raise FileNotFoundError(
                f"Video not found. yt-dlp stderr:\n{result.stderr}"
            )

    sub = _find_subtitle(output_dir, video_id)
    if not sub:
        raise FileNotFoundError(
            "No subtitles downloaded. "
            "This video may not have any subtitles available."
        )

    return DownloadResult(
        video_path=video_path,
        subtitle_path=sub[0],
        title=title,
        sub_lang=sub[1],
    )
