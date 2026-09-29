"""Import known morphs from a running Anki desktop's mature Chinese cards.

Uses the AnkiConnect endpoint already reached by `autoanki --ankiconnect`.
Mature = card interval ≥ 21 days (AnkiMorphs convention).
"""

from __future__ import annotations

import re

import jieba

from autoanki.ankiconnect import _invoke

_HAN_RE = re.compile(r"[一-鿿]")


def _has_chinese(text: str) -> bool:
    return bool(_HAN_RE.search(text))


def scan_mature_morphs(deck_filter: str | None = None) -> set[str]:
    """Query Anki for mature cards, tokenise their Chinese fields, return the morph set.

    `deck_filter`: an Anki deck-name substring to narrow the scan (e.g.
    "Chinese Core 2000"). None means every deck.
    """
    query_parts = ["prop:ivl>=21"]
    if deck_filter:
        query_parts.append(f'"deck:{deck_filter}"')
    query = " ".join(query_parts)

    card_ids = _invoke("findCards", query=query)
    if not card_ids:
        return set()

    # cardsInfo returns note ids alongside cards; batch through notesInfo.
    cards = _invoke("cardsInfo", cards=card_ids)
    note_ids = sorted({c["note"] for c in cards})

    morphs: set[str] = set()
    # notesInfo is happy with large batches; 500 at a time is safe.
    for i in range(0, len(note_ids), 500):
        batch = note_ids[i : i + 500]
        notes = _invoke("notesInfo", notes=batch)
        for note in notes:
            for field_name, field_data in note.get("fields", {}).items():
                value = field_data.get("value", "")
                if not _has_chinese(value):
                    continue
                for tok in jieba.cut(value):
                    if _HAN_RE.search(tok):
                        morphs.add(tok)

    return morphs
