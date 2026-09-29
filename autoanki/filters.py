"""Noise predicates: detect non-dialogue subtitle content.

Six categories are recognised. Each `is_*` predicate returns True when the
text should be dropped from the deck. Compose them via `is_noise()` for the
default drop-everything path; the pipeline exposes `--keep-noise` to skip
all six for users who want the raw stream.

Two natural insertion points (see `notes/decisions/filters-noise-classifier.md`):

- `autoanki/subtitles.parse_vtt` — pre-OCR, English side. Cheapest.
  Predicates safe here: `is_bracketed`, `is_song_lyric_marker`,
  `is_credit_marker`.
- `autoanki/cli._process_one` after OCR/correct — CJK side. Predicates that
  need the Chinese text: `is_cjk_watermark`, `is_cjk_song_marker`,
  `is_repeated_static` (needs the whole batch to spot cross-frame overlays).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

# --- English side (pre-OCR) --------------------------------------------------

_BRACKETED_RE = re.compile(r"^\s*[\[\(（【].*[\]\)）】]\s*$")

_EN_SONG_MARKERS = re.compile(
    r"(?i)(?:^|\s)(?:♪|♫|\[music\]|\[singing\]|performed by|composed by)(?:\s|$)"
)

_EN_CREDIT_MARKERS = re.compile(
    r"(?i)\b(?:directed by|written by|produced by|starring|cinematography|"
    r"executive producer|screenplay|edited by|original music by)\b"
)


def is_bracketed(text: str) -> bool:
    """Whole line wrapped in brackets/parens (`[Episode 01]`, `(笑)`, `【片头曲】`).

    Chinese full-width brackets included.
    """
    return bool(_BRACKETED_RE.match(text))


def is_song_lyric_marker(text: str) -> bool:
    """♪/♫ or explicit song-attribution phrasing on the English side."""
    return bool(_EN_SONG_MARKERS.search(text))


def is_credit_marker(text: str) -> bool:
    """Opening/closing credit attributions on the English side."""
    return bool(_EN_CREDIT_MARKERS.search(text))


# --- CJK side (post-OCR/correct) --------------------------------------------

# Broadcaster / studio watermarks and staff-caption labels.
_CJK_WATERMARK_RE = re.compile(
    r"华策(?:影视|TV|FILMTV)"
    r"|@\w+"
    r"|WX(?:许红豆)?"     # OCR-picked chat handle overlays from Meet Yourself
    r"|优酷|爱奇艺|腾讯视频|芒果TV|B站|哔哩哔哩"
)

# Chinese song / lyric / credit vocabulary that shouldn't drive a study card.
_CJK_SONG_CREDIT_RE = re.compile(
    r"演唱[:：]|作词[:：]|作曲[:：]|编曲[:：]|歌词[:：]|主题曲"
    r"|片头曲|片尾曲|插曲|翻唱|原唱"
    r"|导演[:：]|编剧[:：]|制片[:：]|监制[:：]|出品[:：]"
    r"|字幕组|翻译[:：]|校对[:：]|时间轴"
)

# Full-line Chinese-bracketed (stage directions, sound effects: (笑), （掌声）).
_CJK_BRACKETED_RE = re.compile(r"^[（【].{1,6}[）】]$")


def is_cjk_watermark(text: str) -> bool:
    return bool(_CJK_WATERMARK_RE.search(text))


def is_cjk_song_marker(text: str) -> bool:
    return bool(_CJK_SONG_CREDIT_RE.search(text))


def is_cjk_stage_direction(text: str) -> bool:
    """Short parenthetical stage direction in Chinese brackets."""
    return bool(_CJK_BRACKETED_RE.match(text))


def repeated_texts(texts: Iterable[str], threshold: int = 3) -> set[str]:
    """The subset of `texts` that appears at least `threshold` times.

    Repeated identical OCR across many segments is almost always a static
    overlay (title card, unremoved watermark, "END" screen) rather than a
    line of dialogue somebody happens to say four times.
    """
    counts = Counter(t for t in texts if t)
    return {t for t, n in counts.items() if n >= threshold}


# --- Composition -------------------------------------------------------------


def is_noise_pre_ocr(text: str) -> tuple[bool, str]:
    """Pre-OCR/English-side noise check. Returns (is_noise, reason)."""
    if is_bracketed(text):
        return True, "bracketed"
    if is_song_lyric_marker(text):
        return True, "song-marker"
    if is_credit_marker(text):
        return True, "credit-marker"
    return False, ""


def is_noise_post_ocr(text: str, repeated: set[str]) -> tuple[bool, str]:
    """Post-OCR/CJK-side noise check. Returns (is_noise, reason).

    `repeated` is the output of `repeated_texts` over the whole batch.
    """
    if text in repeated:
        return True, "repeated-static"
    if is_cjk_watermark(text):
        return True, "cjk-watermark"
    if is_cjk_song_marker(text):
        return True, "cjk-song-marker"
    if is_cjk_stage_direction(text):
        return True, "cjk-stage-direction"
    return False, ""
