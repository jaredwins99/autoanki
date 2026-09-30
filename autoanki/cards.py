"""Generate Anki .apkg decks with embedded video clips."""

import hashlib
from pathlib import Path

import genanki
import jieba

from autoanki.morph import highlight_first_unknown, load_known_morphs
from autoanki.pinyin import pinyin_ruby
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
        {"name": "Pinyin"},
    ],
    templates=[
        {
            "name": "Listening",
            "qfmt": "{{Video}}<br><br>What did they say?",
            "afmt": '{{FrontSide}}<hr id="answer">'
            "<p>{{#am-highlighted}}{{am-highlighted}}{{/am-highlighted}}"
            "{{^am-highlighted}}{{Chinese}}{{/am-highlighted}}</p>"
            '<p class="py">{{#Pinyin}}{{Pinyin}}{{/Pinyin}}{{^Pinyin}}{{SegmentedChinese}}{{/Pinyin}}</p>'
            '<p style="color: #888;">{{English}}</p>',
        },
        {
            "name": "Reading",
            "qfmt": '<p style="font-size: 1.5em;">'
            "{{#am-highlighted}}{{am-highlighted}}{{/am-highlighted}}"
            "{{^am-highlighted}}{{Chinese}}{{/am-highlighted}}</p>",
            "afmt": '{{FrontSide}}<hr id="answer">'
            "{{Video}}"
            '<p class="py">{{#Pinyin}}{{Pinyin}}{{/Pinyin}}{{^Pinyin}}{{SegmentedChinese}}{{/Pinyin}}</p>'
            '<p style="color: #888;">{{English}}</p>',
        },
    ],
    css=".card {\n"
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
    "}\n"
    ".py { color: #555; font-size: 0.95em; }\n"
    ".py ruby { margin: 0 0.2em; }\n"
    ".py rt { color: #888; font-size: 0.65em; }",
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
    deck_root: str = "AutoAnki",
    show: str | None = None,
    episode: str | None = None,
    known: set[str] | None = None,
) -> Path:
    """Generate .apkg deck with embedded video clips.

    Deck name is `{deck_root}::{show}::{episode}` when show is given (with
    episode optional); falls back to `{deck_root}::{title}` for backwards
    compatibility with callers that don't yet parse show/episode.
    """
    from autoanki.naming import build_deck_name

    if show is not None:
        deck_name = build_deck_name(deck_root, show, episode)
        deck_id_key = deck_name
    else:
        deck_name = f"{deck_root}::{title}"
        deck_id_key = title
    deck = genanki.Deck(_deck_id_from_title(deck_id_key), deck_name)
    media_files = []
    seen_texts: set[str] = set()
    if known is None:
        known = load_known_morphs()

    for seg, translation, clip_path in zip(segments, translations, clip_paths):
        if not seg.text.strip():
            continue
        if seg.text in seen_texts:
            continue
        seen_texts.add(seg.text)

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
                "",  # am-unknowns (AnkiMorphs Recalc overwrites)
                "",  # am-unknowns-count
                highlight_first_unknown(seg.text, known),
                "",  # am-score
                pinyin_ruby(seg.text),
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
