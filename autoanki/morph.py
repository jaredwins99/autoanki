"""Focus-morph highlighting: wrap the first unknown morph in an AnkiMorphs-compatible span."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import jieba

DEFAULT_KNOWN_CSV = Path(__file__).resolve().parent.parent / "data" / "hsk1-5_known_morphs.csv"

_HAN_RE = re.compile(r"[一-鿿]")


def load_known_morphs(csv_path: Path = DEFAULT_KNOWN_CSV) -> set[str]:
    """Load the known-morphs CSV (Morph-Lemma column) into a set."""
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["Morph-Lemma"] for row in reader if row.get("Morph-Lemma")}


def highlight_first_unknown(text: str, known: set[str]) -> str:
    """Wrap the first unknown Chinese morph in a morph-status span.

    Returns AnkiMorphs-compatible HTML — the `am-highlighted` field format.
    If every morph is known (or none contain Chinese), returns the plain text.
    """
    if not text:
        return ""

    tokens = list(jieba.cut(text))
    highlighted = False
    parts: list[str] = []

    for tok in tokens:
        if not highlighted and _HAN_RE.search(tok) and tok not in known:
            parts.append(f'<span morph-status="unknown">{tok}</span>')
            highlighted = True
        else:
            parts.append(tok)

    return "".join(parts)
