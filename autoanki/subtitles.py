"""VTT subtitle parsing with YouTube auto-sub deduplication."""

import re
from dataclasses import dataclass
from pathlib import Path

import webvtt


@dataclass
class Segment:
    index: int
    start: float
    end: float
    text: str


def _timestamp_to_seconds(ts: str) -> float:
    """Convert VTT timestamp '00:01:23.456' to float seconds."""
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


def _clean_text(text: str) -> str:
    """Strip HTML tags, control chars, and normalize whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\u200b", "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def parse_vtt(vtt_path: Path, require_chinese: bool = True) -> list[Segment]:
    """Parse VTT file into deduplicated segments."""
    captions = list(webvtt.read(str(vtt_path)))

    raw = []
    for cap in captions:
        text = _clean_text(cap.text)
        if not text:
            continue
        start = _timestamp_to_seconds(cap.start)
        end = _timestamp_to_seconds(cap.end)
        raw.append((start, end, text))

    # Deduplicate YouTube rolling captions (first line repeats previous last line)
    deduped = []
    for i, (start, end, text) in enumerate(raw):
        lines = text.split("\n")
        if i > 0:
            prev_lines = raw[i - 1][2].split("\n")
            if lines and prev_lines and lines[0].strip() == prev_lines[-1].strip():
                lines = lines[1:]
        merged = " ".join(l.strip() for l in lines if l.strip())
        if merged:
            deduped.append((start, end, merged))

    merged = []
    for start, end, text in deduped:
        if merged and merged[-1][2] == text:
            merged[-1] = (merged[-1][0], end, text)
        else:
            merged.append((start, end, text))

    segments = []
    idx = 0
    for start, end, text in merged:
        if end - start < 0.3:
            continue
        if require_chinese and not _has_chinese(text):
            continue
        segments.append(Segment(index=idx, start=start, end=end, text=text))
        idx += 1

    return segments
