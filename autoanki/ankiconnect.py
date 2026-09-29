"""Push Anki flashcards via AnkiConnect addon.

URL is configurable via ANKICONNECT_URL env var (default http://localhost:8765).
Change the AnkiConnect port in Tools > Add-ons > AnkiConnect > Config
(webBindPort) if 8765 clashes with another service on your machine.
"""

import base64
import json
import os
import urllib.request
from pathlib import Path

import jieba

from autoanki.morph import highlight_first_unknown, load_known_morphs
from autoanki.subtitles import Segment

ANKICONNECT_URL = os.environ.get("ANKICONNECT_URL", "http://localhost:8555")

MODEL_NAME = "AutoAnki Chinese"
FIELDS = [
    "Chinese", "English", "Video", "SegmentedChinese", "Index",
    "am-unknowns", "am-unknowns-count", "am-highlighted", "am-score",
]

CSS = (
    ".card {\n"
    '  font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;\n'
    "  font-size: 20px;\n"
    "  text-align: center;\n"
    "  color: #333;\n"
    "  background-color: #fff;\n"
    "}\n"
    '[morph-status="unknown"], .am-unknown {\n'
    "  color: #fbc02d;\n"
    "  font-weight: 600;\n"
    "}\n"
    '[morph-status="unset"] {\n'
    "  color: #888;\n"
    "}"
)

_ZH_CELL = (
    "{{#am-highlighted}}{{am-highlighted}}{{/am-highlighted}}"
    "{{^am-highlighted}}{{Chinese}}{{/am-highlighted}}"
)

TEMPLATES = [
    {
        "Name": "Listening",
        "Front": "{{Video}}<br><br>What did they say?",
        "Back": (
            '{{FrontSide}}<hr id="answer">'
            f"<p>{_ZH_CELL}</p>"
            '<p style="color: #666; font-size: 0.9em;">{{SegmentedChinese}}</p>'
            '<p style="color: #888;">{{English}}</p>'
        ),
    },
    {
        "Name": "Reading",
        "Front": f'<p style="font-size: 1.5em;">{_ZH_CELL}</p>',
        "Back": (
            '{{FrontSide}}<hr id="answer">'
            "{{Video}}"
            '<p style="color: #666; font-size: 0.9em;">{{SegmentedChinese}}</p>'
            '<p style="color: #888;">{{English}}</p>'
        ),
    },
]


def _invoke(action: str, **params) -> dict:
    """HTTP POST to AnkiConnect (v6 protocol)."""
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(
        ANKICONNECT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise ConnectionError(
            "Cannot connect to Anki. Is Anki running with AnkiConnect installed? "
            f"(expected at {ANKICONNECT_URL}): {e}"
        ) from e

    if result.get("error"):
        raise RuntimeError(f"AnkiConnect error: {result['error']}")
    return result.get("result")


def _ensure_model() -> None:
    """Create 'AutoAnki Chinese' note type, or update its fields/templates/CSS if it already exists."""
    existing = _invoke("modelNames")
    if MODEL_NAME not in existing:
        _invoke(
            "createModel",
            modelName=MODEL_NAME,
            inOrderFields=FIELDS,
            css=CSS,
            cardTemplates=TEMPLATES,
        )
        return

    # Model exists — add any fields the template needs but the model is missing,
    # then sync templates and CSS.
    current_fields = _invoke("modelFieldNames", modelName=MODEL_NAME)
    for field in FIELDS:
        if field not in current_fields:
            _invoke("modelFieldAdd", modelName=MODEL_NAME, fieldName=field, index=len(current_fields))
            current_fields.append(field)

    _invoke(
        "updateModelTemplates",
        model={
            "name": MODEL_NAME,
            "templates": {t["Name"]: {"Front": t["Front"], "Back": t["Back"]} for t in TEMPLATES},
        },
    )
    _invoke("updateModelStyling", model={"name": MODEL_NAME, "css": CSS})


def _store_media(clip_path: Path) -> str:
    """Base64-encode and push a video/audio clip to Anki's collection.media."""
    data = clip_path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    filename = clip_path.name
    _invoke("storeMediaFile", filename=filename, data=encoded)
    return filename


def _segment_chinese(text: str) -> str:
    """Segment Chinese text with jieba, matching cards.py format."""
    return " / ".join(jieba.cut(text))


def push_to_anki(
    title: str,
    segments: list[Segment],
    translations: list[str],
    clip_paths: list[Path],
) -> int:
    """Create deck, ensure model, push notes. Returns count of notes added/updated."""
    deck_name = f"AutoAnki::{title}"

    # Ensure deck and model exist
    _invoke("createDeck", deck=deck_name)
    _ensure_model()

    known = load_known_morphs()
    count = 0
    total = len(segments)

    for i, (seg, translation, clip_path) in enumerate(
        zip(segments, translations, clip_paths)
    ):
        print(f"  [{i + 1}/{total}] {seg.text[:40]}...")

        # Store media file
        clip_filename = _store_media(clip_path)

        fields = {
            "Chinese": seg.text,
            "English": translation,
            "Video": f"[sound:{clip_filename}]",
            "SegmentedChinese": _segment_chinese(seg.text),
            "Index": str(seg.index),
            "am-highlighted": highlight_first_unknown(seg.text, known),
        }

        # Try to find existing note (duplicate check by Chinese field in this deck)
        existing = _invoke(
            "findNotes",
            query=f'"deck:{deck_name}" "Chinese:{seg.text}"',
        )

        if existing:
            # Update existing note
            _invoke(
                "updateNoteFields",
                note={"id": existing[0], "fields": fields},
            )
        else:
            # Add new note
            _invoke(
                "addNote",
                note={
                    "deckName": deck_name,
                    "modelName": MODEL_NAME,
                    "fields": fields,
                    "options": {"allowDuplicate": False},
                },
            )

        count += 1

    print(f"Done: {count} notes added/updated in '{deck_name}'.")
    return count
