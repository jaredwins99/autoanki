"""Download video + Chinese subtitles from YouTube/Bilibili via yt-dlp."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadResult:
    video_path: Path
    subtitle_path: Path
    title: str
    sub_lang: str  # language code of downloaded subs, e.g. "zh-Hans", "en"


def download(url: str, output_dir: Path) -> DownloadResult:
    """Download video + Chinese subtitles from URL via yt-dlp."""
    output_dir.mkdir(parents=True, exist_ok=True)

    sub_langs = "zh-Hans,zh,zh-CN,zh-Hant,zh-TW,zh-Hans-en,zh-Hant-en,en"
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
        url,
    ]

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

    subtitle_path = None
    sub_lang = None
    preferred_order = [
        "zh-Hans", "zh", "zh-CN", "zh-Hant", "zh-TW",
        "zh-Hans-en", "zh-Hant-en",
        "en",
    ]
    for lang in preferred_order:
        candidate = output_dir / f"{video_id}.{lang}.vtt"
        if candidate.exists():
            subtitle_path = candidate
            sub_lang = lang
            break

    if not subtitle_path:
        candidates = list(output_dir.glob(f"{video_id}*.vtt"))
        if candidates:
            subtitle_path = candidates[0]
            sub_lang = subtitle_path.stem.split(".", 1)[-1] if "." in subtitle_path.stem else "unknown"
        else:
            raise FileNotFoundError(
                "No subtitles downloaded. "
                "This video may not have any subtitles available."
            )

    return DownloadResult(
        video_path=video_path,
        subtitle_path=subtitle_path,
        title=title,
        sub_lang=sub_lang,
    )
