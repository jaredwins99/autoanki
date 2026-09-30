# autoanki Architecture

What each piece is and how data flows. *Why* each piece is the way it is
lives in `notes/decisions/` (one note per module, indexed in
`notes/INDEX.md`). This file deliberately holds no rationale, so it has
less to drift.

## Repository layout

```
autoanki/                      Python package (the pipeline)
├── cli.py                     entry point; `autoanki <url>` and `autoanki setup`
├── download.py                yt-dlp: video + subtitle tracks, cached by video id
├── subtitles.py               VTT → [Segment]; dedup, junk + pre-OCR noise filter
├── filters.py                 noise predicates (songs, credits, watermarks, stage directions, repeats)
├── clip.py                    ffmpeg: one mp4 per segment, padded
├── ocr.py                     PaddleOCR on burned-in subs (bottom-crop + Y-band filter)
├── ocr_correct.py             Claude post-pass fixing OCR against the English line
├── ocr_preprocessing.py       Claude EN→ZH fallback when OCR is off or mostly empty
├── translate.py               Claude ZH→EN when the video has real Chinese subs
├── morph.py                   known-morph loading, unknown detection, first-unknown highlight
├── pinyin.py                  tone-marked pinyin per word, as ruby, for the card back
├── audio_lang.py              spoken-language ID per clip (Whisper) to drop non-Mandarin audio
├── vocab_judge.py             agent pass: unknown token → name / transparent / artifact / vocab
├── hsk.py                     inline HSK word list + generator for the baseline CSV
├── naming.py                  video title → (show, episode) → Anki deck name
├── cards.py                   .apkg writer (genanki)
├── ankiconnect.py             live push into a running Anki; syncs the note type
└── level/
    ├── profile.py             Profile (known morphs) ↔ ~/.config/autoanki/profile.yaml
    ├── anki_import.py         mature-card (ivl≥21) morph scan via AnkiConnect
    └── setup_cli.py           `autoanki setup` wizard (hsk / anki / hybrid; quiz pending)
data/hsk1-5_known_morphs.csv   baseline known set (36,586 morphs)
notes/                         decisions / findings / open / reference + generated INDEX.md
correctness/                   checks/check_notes.py, hooks/notes-gate.sh
legibility/                    decision-notes.md (note standard), docs/ (this file, process.md)
scripts/                       make_demo_gif.py, linear.sh
plans/                         mvp-pipeline.md (historical)
```

## Pipeline

```
URL
 │ download.py ─────────── video.mp4 + best subtitle track (zh preferred, else en)
 ▼
subtitles.parse_vtt ────── [Segment]   dedup rolling captions, drop short/junk,
 │                                     drop pre-OCR noise (filters.is_noise_pre_ocr)
 ▼
clip.extract_clips ─────── clip_NNNN.mp4 per segment (±0.4s default padding)
 │
 ├─ subs are Chinese ──── translate.py        ZH → EN
 └─ subs are English ──── ocr.py              burned-in ZH from frames
                          (ocr_preprocessing  EN → ZH if >50% OCR empty)
                          ocr_correct.py      fix OCR using the EN line
 ▼
noise filter (post-OCR) ── filters.is_noise_post_ocr   watermarks, song/credit
 │                                                     markers, repeated static text
 ▼
vocab judge (agent) ────── non-vocab unknowns (names, transparent combos, artifacts) → known
 ▼
i+1 filter (--i-plus-one)  keep sentences with exactly one unknown morph
 │                         known set = Profile if present, else baseline CSV
 ▼
language filter ────────── audio_lang.spoken_language: keep only clips spoken in Mandarin
 ▼
translate (OCR path) ───── English from each card's own Chinese (translate.py)
 ▼
naming.parse_show_episode  deck = <root>::<show>::<episode>
 ▼
cards.generate_deck (.apkg)   or   ankiconnect.push_to_anki (--ankiconnect)
   am-highlighted = morph.highlight_first_unknown(text, known); Pinyin = pinyin.pinyin_ruby(text)
```

## CLI

```
autoanki <url>... [options]      run the pipeline
autoanki setup [--mode M]        build ~/.config/autoanki/profile.yaml
```

| Flag | Default | Effect |
|---|---|---|
| `-o, --output` | `<title>.apkg` | .apkg path (single URL) |
| `--ankiconnect` | off | push to running Anki instead of writing .apkg |
| `--i-plus-one` | off | keep only sentences with exactly one unknown morph |
| `--keep-noise` | off | disable both noise filter passes |
| `--keep-non-mandarin` | off | skip the spoken-language filter |
| `--no-vocab-judge` | off | skip the agent pass on unknown tokens |
| `--clip-padding` | `0.4` | seconds of buffer before/after each line |
| `--deck-root` | `AutoAnki` | top-level deck |
| `--show`, `--episode` | parsed from title | override deck naming |
| `--no-ocr` | off | Claude EN→ZH instead of OCR |
| `--no-ocr-correct` | off | skip the Claude OCR post-pass |
| `--no-translate` | off | leave English empty (Chinese-sub videos) |
| `--work-dir`, `--keep-work-dir` | temp dir | keep intermediates (clips, OCR cache) |
| `--cookies` | none | cookies file for login-required videos |

Environment: `ANKICONNECT_URL` (default `http://localhost:8555`),
`AUTOANKI_PROFILE` (default `~/.config/autoanki/profile.yaml`),
`AUTOANKI_CACHE` (default `~/.cache/autoanki`; downloads persist in
`<cache>/<video-id>/download/` regardless of `--work-dir`).

## Card model

Note type `AutoAnki Chinese`, two cards per note:

- **Listening**: clip → reveal Chinese (highlighted), word-by-word tone pinyin, English
- **Reading**: Chinese (highlighted) → reveal clip, word-by-word tone pinyin, English

The highlighted Chinese renders `am-highlighted` when set and falls back
to plain `Chinese`; unknown morphs are `<span morph-status="unknown">`,
styled yellow.

## Runtime requirements

ffmpeg, the `claude` CLI (translation/correction), PaddlePaddle +
PaddleOCR (OCR path only), and a JavaScript runtime yt-dlp accepts for
YouTube's challenge: `deno` (pip wheel) with `yt-dlp-ejs>=0.8`.
