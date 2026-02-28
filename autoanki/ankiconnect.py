"""Push Anki flashcards via AnkiConnect addon (localhost:8765)."""

import base64
import json
import urllib.request
from pathlib import Path

import jieba

from autoanki.subtitles import Segment

ANKICONNECT_URL = "http://localhost:8765"

MODEL_NAME = "AutoAnki Chinese"
FIELDS = ["Chinese", "English", "Video", "SegmentedChinese", "Index"]

CSS = (
    ".card {\n"
    '  font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;\n'
    "  font-size: 20px;\n"
    "  text-align: center;\n"
    "  color: #333;\n"
    "  background-color: #fff;\n"
    "}"
)

TEMPLATES = [
    {
        "Name": "Listening",
        "Front": "{{Video}}<br><br>What did they say?",
        "Back": (
            '{{FrontSide}}<hr id="answer">'
            "<p>{{Chinese}}</p>"
            '<p style="color: #666; font-size: 0.9em;">{{SegmentedChinese}}</p>'
            '<p style="color: #888;">{{English}}</p>'
        ),
    },
    {
        "Name": "Reading",
        "Front": '<p style="font-size: 1.5em;">{{Chinese}}</p>',
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
    """Create 'AutoAnki Chinese' note type if it doesn't exist."""
    existing = _invoke("modelNames")
    if MODEL_NAME in existing:
        return

    _invoke(
        "createModel",
        modelName=MODEL_NAME,
        inOrderFields=FIELDS,
        css=CSS,
        cardTemplates=TEMPLATES,
    )


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
