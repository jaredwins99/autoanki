"""OCR extraction of burned-in Chinese subtitles from video frames."""

import subprocess
import re
from pathlib import Path
from PIL import Image
import pytesseract

from autoanki.subtitles import Segment


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


def _crop_subtitle_region(image: Image.Image) -> Image.Image:
    """Crop the bottom portion of the frame where subtitles typically appear."""
    width, height = image.size
    # Subtitles are usually in the bottom 20-25% of the frame
    top = int(height * 0.75)
    return image.crop((0, top, width, height))


def _ocr_chinese(image: Image.Image) -> str:
    """Run tesseract OCR on an image to extract Chinese text."""
    # Use chi_sim (simplified) + chi_tra (traditional) for best coverage
    text = pytesseract.image_to_string(image, lang="chi_sim+chi_tra")
    # Clean up OCR output
    text = text.strip()
    text = re.sub(r'\s+', '', text)  # Chinese text doesn't use spaces
    # Remove non-Chinese characters that are likely OCR noise
    # Keep Chinese chars, common punctuation
    text = re.sub(r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2000-\u206f]', '', text)
    return text


def ocr_segments(
    video_path: Path,
    segments: list[Segment],
    work_dir: Path,
) -> list[str]:
    """Extract Chinese text from burned-in subtitles for each segment.

    Uses the segment timestamps to grab frames, then OCRs the subtitle region.
    Returns a list of Chinese text strings, one per segment.
    """
    frames_dir = work_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    chinese_texts = []

    for i, seg in enumerate(segments):
        # Grab frame from middle of segment for best subtitle visibility
        mid_time = (seg.start + seg.end) / 2
        frame_path = frames_dir / f"frame_{seg.index:04d}.jpg"

        _extract_frame(video_path, mid_time, frame_path)

        # Load, crop subtitle region, OCR
        image = Image.open(frame_path)
        sub_region = _crop_subtitle_region(image)
        chinese_text = _ocr_chinese(sub_region)

        chinese_texts.append(chinese_text)
        print(f"  OCR {i + 1}/{len(segments)}: {chinese_text[:30]}", end="\r")

    print()
    return chinese_texts
