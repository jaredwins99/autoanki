"""Extract video clips from source video using ffmpeg."""

import subprocess
from pathlib import Path

from autoanki.subtitles import Segment


def extract_clips(
    video_path: Path,
    segments: list[Segment],
    output_dir: Path,
    padding: float = 0.15,
) -> list[Path]:
    """Extract one mp4 clip per segment from the source video."""
    output_dir.mkdir(parents=True, exist_ok=True)
    clip_paths = []

    for i, seg in enumerate(segments):
        clip_name = f"clip_{seg.index:04d}.mp4"
        clip_path = output_dir / clip_name

        start = max(0, seg.start - padding)
        end = seg.end + padding

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", f"{start:.3f}",
            "-to", f"{end:.3f}",
            "-i", str(video_path),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-crf", "23",
            "-ac", "1",
            "-ar", "44100",
            "-movflags", "+faststart",
            "-avoid_negative_ts", "make_zero",
            str(clip_path),
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        clip_paths.append(clip_path)
        print(f"  clip {i + 1}/{len(segments)}", end="\r")

    print()
    return clip_paths
