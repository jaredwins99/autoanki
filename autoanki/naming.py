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

# Divider/label residue after episode is stripped.
_TAIL_SEPARATORS = re.compile(r"[\s\-\|:：]+$")


def _strip_tail_junk(text: str) -> str:
    return _TAIL_SEPARATORS.sub("", _JUNK_TAILS.sub("", text)).strip()


def parse_show_episode(video_title: str) -> tuple[str, Optional[str]]:
    """Best-effort split of a video title into (show, episode).

    Episode is normalised to zero-padded `EP\\d{2}` (or `S\\d{2}E\\d{2}` for
    season-shaped labels). Show is what remains after removing the episode
    token and trailing bracketed tags.
    """
    remainder = _JUNK_TAILS.sub("", video_title).strip()
    episode: Optional[str] = None
    for pattern, formatter in _EPISODE_PATTERNS:
        match = pattern.search(remainder)
        if match:
            episode = formatter(match)
            # Everything after the episode marker is typically an episode
            # subtitle ("The Return") or a repost tag — drop it. The show is
            # what appears before the marker.
            remainder = remainder[:match.start()]
            break
    show = _strip_tail_junk(remainder)
    return show or video_title.strip(), episode


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
