"""Generate Anki .apkg decks with embedded video clips."""

import hashlib
from pathlib import Path

import genanki
import jieba

from autoanki.subtitles import Segment

AUTOANKI_MODEL_ID = 1607392319

AUTOANKI_MODEL = genanki.Model(
    AUTOANKI_MODEL_ID,
    "AutoAnki Chinese",
    fields=[
        {"name": "Chinese"},
        {"name": "English"},
        {"name": "Video"},
        {"name": "SegmentedChinese"},
        {"name": "Index"},
        # AnkiMorphs extra fields (populated by AnkiMorphs during Recalc)
        {"name": "am-unknowns"},
        {"name": "am-unknowns-count"},
        {"name": "am-highlighted"},
        {"name": "am-score"},
    ],
    templates=[
        {
            "name": "Listening",
            "qfmt": "{{Video}}<br><br>What did they say?",
            "afmt": '{{FrontSide}}<hr id="answer">'
            "<p>{{Chinese}}</p>"
            '<p style="color: #666; font-size: 0.9em;">{{SegmentedChinese}}</p>'
            '<p style="color: #888;">{{English}}</p>',
        },
        {
            "name": "Reading",
            "qfmt": '<p style="font-size: 1.5em;">{{Chinese}}</p>',
            "afmt": '{{FrontSide}}<hr id="answer">'
            "{{Video}}"
            '<p style="color: #666; font-size: 0.9em;">{{SegmentedChinese}}</p>'
            '<p style="color: #888;">{{English}}</p>',
        },
    ],
    css=".card {\n"
    '  font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;\n'
    "  font-size: 20px;\n"
    "  text-align: center;\n"
    "  color: #333;\n"
    "  background-color: #fff;\n"
    "}",
)


def _deck_id_from_title(title: str) -> int:
    return int(hashlib.md5(title.encode()).hexdigest()[:8], 16)


def _note_guid(video_title: str, index: int) -> str:
    raw = f"autoanki::{video_title}::{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:10]


def _segment_chinese(text: str) -> str:
    return " / ".join(jieba.cut(text))


def generate_deck(
    title: str,
    segments: list[Segment],
    translations: list[str],
    clip_paths: list[Path],
    output_path: Path,
) -> Path:
    """Generate .apkg deck with embedded video clips."""
    deck = genanki.Deck(_deck_id_from_title(title), f"AutoAnki::{title}")
    media_files = []

    for seg, translation, clip_path in zip(segments, translations, clip_paths):
        if not seg.text.strip():
            continue

        clip_filename = clip_path.name
        media_files.append(str(clip_path))

        note = genanki.Note(
            model=AUTOANKI_MODEL,
            fields=[
                seg.text,
                translation,
                f"[sound:{clip_filename}]",
                _segment_chinese(seg.text),
                str(seg.index),
                "",  # am-unknowns (filled by AnkiMorphs)
                "",  # am-unknowns-count
                "",  # am-highlighted
                "",  # am-score
            ],
            sort_field=str(seg.index),
            guid=_note_guid(title, seg.index),
        )
        deck.add_note(note)

    package = genanki.Package(deck)
    package.media_files = media_files

    output_path.parent.mkdir(parents=True, exist_ok=True)
    package.write_to_file(str(output_path))

    return output_path
