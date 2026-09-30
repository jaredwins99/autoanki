"""OCR extraction of burned-in Chinese subtitles from video frames using PaddleOCR."""

import concurrent.futures
import json
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from autoanki.subtitles import Segment

# oneDNN off: paddlepaddle 3.3 + PaddleOCR 3.4 raise NotImplementedError in
# the oneDNN executor on the first predict. Without oneDNN the server models
# take ~10s/frame on CPU; the mobile models take ~2s with the same text on
# clean subtitle crops.
_ocr = PaddleOCR(
    lang="ch",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    enable_mkldnn=False,
    cpu_threads=os.cpu_count() or 4,
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
)


def _extract_frame(video_path: Path, timestamp: float, output_path: Path) -> Path:
    """Extract a single frame from video at given timestamp using ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{timestamp:.3f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def _crop_subtitle_region(image: np.ndarray) -> np.ndarray:
    """Crop the bottom 20-25% of the frame where subtitles typically appear."""
    h, w = image.shape[:2]
    top = int(h * 0.75)
    return image[top:h, 0:w]


def _is_subtitle(poly, w, h, score):
    """Check if a detected text region looks like a subtitle line.

    Uses vertical position as the primary filter: burned-in subtitles appear
    in a narrow Y band (~30% down the bottom-25% crop), while background text
    (signs, documents, character name labels) appears elsewhere.
    """
    cy = sum(p[1] for p in poly) / len(poly)
    cx = (min(p[0] for p in poly) + max(p[0] for p in poly)) / 2

    if score < 0.5:
        return False
    # Subtitle Y band: cy must be between 20%-45% of crop height
    # Subtitles consistently appear at cy ≈ 0.32
    if cy < h * 0.20 or cy > h * 0.45:
        return False
    # Center must be in middle 80% of frame width
    if cx < w * 0.10 or cx > w * 0.90:
        return False
    return True


def _ocr_chinese(image: np.ndarray) -> str:
    """Run PaddleOCR on a color image, returning only subtitle text.

    Filters out background text (signs, documents) using Y-band
    positioning and horizontal centering.
    """
    result = _ocr.predict(image)
    if not result or not result[0]:
        return ""

    h, w = image.shape[:2]
    texts = result[0].get("rec_texts", [])
    scores = result[0].get("rec_scores", [])
    polys = result[0].get("dt_polys", [])

    filtered: list[tuple[float, str]] = []
    for text, score, poly in zip(texts, scores, polys):
        if _is_subtitle(poly, w, h, score):
            cy = sum(p[1] for p in poly) / len(poly)
            filtered.append((cy, text))

    filtered.sort(key=lambda t: t[0])
    return "".join(text for _, text in filtered).strip()


def ocr_segments(
    video_path: Path,
    segments: list[Segment],
    work_dir: Path,
    max_workers: int = 4,
) -> list[str]:
    """Extract Chinese text from burned-in subtitles for each segment.

    Caches results to ocr_cache.json. Parallelizes frame extraction
    for uncached segments, then runs PaddleOCR sequentially.
    """
    frames_dir = work_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    cache_path = work_dir / "ocr_cache.json"
    cache: dict[str, str] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())

    uncached = [s for s in segments if f"frame_{s.index:04d}" not in cache]
    cached_count = len(segments) - len(uncached)

    if uncached:
        print(f"  Extracting {len(uncached)} frames ({cached_count} cached)...")

        def extract_one(seg: Segment) -> None:
            mid_time = (seg.start + seg.end) / 2
            _extract_frame(video_path, mid_time, frames_dir / f"frame_{seg.index:04d}.jpg")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(extract_one, uncached))

        for i, seg in enumerate(uncached):
            cache_key = f"frame_{seg.index:04d}"
            image = cv2.imread(str(frames_dir / f"frame_{seg.index:04d}.jpg"))
            sub_region = _crop_subtitle_region(image)
            cache[cache_key] = _ocr_chinese(sub_region)
            print(f"  OCR {i + 1}/{len(uncached)}: {cache[cache_key]}", end="\r")
            if (i + 1) % 25 == 0:  # a crash mid-run keeps what's done
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        print()

    if cached_count:
        print(f"  ({cached_count} cached, {len(uncached)} new)")

    return [cache.get(f"frame_{s.index:04d}", "") for s in segments]
