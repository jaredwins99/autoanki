"""Parse a video title into (show, episode) so multi-episode runs land in nested subdecks.

Handles common patterns seen on YouTube and Bilibili Chinese TV uploads:

    "Meet Yourself EP1 [Eng Sub]"        -> ("Meet Yourself", "EP01")
    "去有风的地方 第1集"                    -> ("去有风的地方", "EP01")
    "Meet Yourself Episode 01"           -> ("Meet Yourself", "EP01")
    "Meet Yourself S01E03 - The Return"  -> ("Meet Yourself", "S01E03")
    "去有风的地方"                          -> ("去有风的地方", None)     # no episode marker

When no episode marker is found the show is returned verbatim (post-cleanup)
and episode is None. Callers decide whether that constitutes an error or is
fine (a one-off video that isn't part of a series).
"""

from __future__ import annotations

import re
from typing import Optional

# Order matters: SNNENN before EPNN before naked NN.
_EPISODE_PATTERNS = [
    (re.compile(r"\b(S\d{1,2}E\d{1,3})\b", re.IGNORECASE), lambda m: m.group(1).upper()),
    (re.compile(r"\bEP(?:ISODE)?\s*[.:# ]?\s*(\d{1,3})\b", re.IGNORECASE),
     lambda m: f"EP{int(m.group(1)):02d}"),
    (re.compile(r"\bE(\d{1,3})\b"), lambda m: f"EP{int(m.group(1)):02d}"),
    (re.compile(r"第\s*(\d{1,3})\s*集"), lambda m: f"EP{int(m.group(1)):02d}"),
]

# Junk suffixes typically found on YouTube titles: [Eng Sub], (HD), etc.
_JUNK_TAILS = re.compile(r"[\[\(（].*?[\]\)）]")

# Chinese broadcasters wrap the show name itself: 【去有风的地方】, 《去有风的地方》.
_TITLE_BRACKETS = re.compile(r"[【《](.+?)[】》]")

# Broadcaster titles separate name / cast / English title with pipes.
_SEGMENT_SPLIT = re.compile(r"\s*[|｜]\s*")

# Divider/label residue after episode is stripped.
_TAIL_SEPARATORS = re.compile(r"[\s\-\|:：]+$")


def _strip_tail_junk(text: str) -> str:
    return _TAIL_SEPARATORS.sub("", _JUNK_TAILS.sub("", text)).strip()


def _clean_show(text: str) -> str:
    return _strip_tail_junk(_TITLE_BRACKETS.sub(r"\1", text))


def _find_episode(text: str) -> Optional[re.Match]:
    """Earliest episode marker in `text`, with its formatter; SxxExx wins ties."""
    best = None
    for pattern, formatter in _EPISODE_PATTERNS:
        match = pattern.search(text)
        if match and (best is None or match.start() < best[0].start()):
            best = (match, formatter)
    return best


def parse_show_episode(video_title: str) -> tuple[str, Optional[str]]:
    """Best-effort split of a video title into (show, episode).

    Episode is normalised to zero-padded `EP\\d{2}` (or `S\\d{2}E\\d{2}` for
    season-shaped labels). The title is split on `|`; the first segment that
    carries an episode marker supplies both, with the show being what comes
    before the marker. If that segment has nothing before its marker, the
    first marker-free segment is the show.
    """
    segments = [s for s in _SEGMENT_SPLIT.split(video_title) if s.strip()] or [video_title]
    cleaned = [_JUNK_TAILS.sub("", s).strip() for s in segments]

    for seg in cleaned:
        found = _find_episode(seg)
        if not found:
            continue
        match, formatter = found
        # Everything after the marker is an episode subtitle ("The Return")
        # or a repost tag; the show is what comes before it.
        show = _clean_show(seg[:match.start()])
        if not show:
            show = next((_clean_show(s) for s in cleaned if not _find_episode(s) and _clean_show(s)), "")
        return show or video_title.strip(), formatter(match)

    return _clean_show(cleaned[0]) or video_title.strip(), None


def build_deck_name(deck_root: str, show: str, episode: Optional[str]) -> str:
    """Compose the final Anki deck name.

    - `{deck_root}::{show}::{episode}` when the episode is known.
    - `{deck_root}::{show}` when it isn't (one-off video).

    Both `show` and `episode` have `::` stripped so a stray double-colon in a
    parsed title doesn't produce an unintended nesting level.
    """
    parts = [deck_root.replace("::", "-"), show.replace("::", "-")]
    if episode:
        parts.append(episode.replace("::", "-"))
    return "::".join(parts)
