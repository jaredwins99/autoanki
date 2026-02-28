# autoanki Architecture

## Project Tree

```
autoanki/
├── autoanki/                  # Python package
│   ├── __init__.py            # Version string ("0.1.0")
│   ├── cli.py                 # CLI entry point — orchestrates the full pipeline
│   ├── download.py            # Downloads video + subtitles via yt-dlp
│   ├── subtitles.py           # Parses VTT subs, deduplicates YouTube rolling captions
│   ├── clip.py                # Extracts per-segment mp4 clips via ffmpeg
│   ├── ocr.py                 # Extracts burned-in Chinese text from video frames (PaddleOCR)
│   ├── ocr_preprocessing.py   # Translates English subs → Chinese via Claude CLI (OCR fallback)
│   ├── translate.py           # Translates Chinese subs → English via Claude CLI
│   └── cards.py               # Generates .apkg Anki deck with embedded video clips
├── scripts/
│   └── linear.sh              # Linear issue tracker API (direct curl, no MCP)
├── plans/
│   └── mvp-pipeline.md        # MVP pipeline design doc
├── pyproject.toml             # Package config, dependencies, entry point
├── CLAUDE.md                  # Agent system instructions and project rules
├── README.md                  # Project readme
└── .gitignore
```

## Pipeline Flow

```
                         ┌──────────────────────────────────┐
                         │           CLI (cli.py)            │
                         │   Parses args, orchestrates all   │
                         └──────────────┬───────────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
           Stage 1  │         download.py                    │
                    │  URL ──► yt-dlp ──► video.mp4          │
                    │                  ──► subs.vtt           │
                    │         Returns DownloadResult          │
                    └───────────────────┬───────────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
           Stage 2  │         subtitles.py                   │
                    │  subs.vtt ──► parse ──► deduplicate    │
                    │           ──► filter ──► [Segment]     │
                    └───────────────────┬───────────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
           Stage 3  │         clip.py                        │
                    │  video.mp4 + [Segment] ──► ffmpeg      │
                    │           ──► clip_0000.mp4, ...       │
                    └───────────────────┬───────────────────┘
                                        │
                         ┌──────────────▼──────────────┐
                         │  Chinese subs available?     │
                         └──┬──────────────────────┬───┘
                       YES  │                      │  NO
                            ▼                      ▼
              ┌─────────────────────┐  ┌─────────────────────────┐
     Stage 4a │   translate.py      │  │  ocr.py                  │
              │ Chinese ──► English │  │  Frames ──► PaddleOCR    │
              │ via Claude CLI      │  │  ──► Chinese text         │
              └─────────┬───────────┘  │                           │
                        │              │  If >50% empty:           │
                        │              │  ocr_preprocessing.py     │
                        │              │  English ──► Chinese      │
                        │              │  via Claude CLI            │
                        │              └─────────┬─────────────────┘
                        │                        │
                        └──────────┬─────────────┘
                                   │
                    ┌──────────────▼────────────────────┐
           Stage 5  │         cards.py                    │
                    │  [Segment] + translations + clips   │
                    │  ──► genanki ──► output.apkg        │
                    │  jieba segments Chinese for display  │
                    └─────────────────────────────────────┘
```

## Module Reference

### `cli.py`

**Purpose:** CLI entry point that wires together all pipeline stages.

| Function | Description |
|----------|-------------|
| `main()` | Parses CLI args, runs stages 1-5 in sequence, manages temp directory cleanup |

**Dependencies:** `download`, `subtitles`, `clip`, `translate`, `cards`, `ocr`, `ocr_preprocessing`

---

### `download.py`

**Purpose:** Downloads video and subtitles from YouTube/Bilibili via yt-dlp.

| Symbol | Description |
|--------|-------------|
| `DownloadResult` | Dataclass holding `video_path`, `subtitle_path`, `title`, `sub_lang` |
| `download(url, output_dir)` | Runs yt-dlp, prefers Chinese subs, falls back to English; returns `DownloadResult` |

**Dependencies:** stdlib only (`json`, `subprocess`, `pathlib`)

---

### `subtitles.py`

**Purpose:** Parses VTT subtitle files into deduplicated, filtered segments.

| Symbol | Description |
|--------|-------------|
| `Segment` | Dataclass: `index`, `start` (seconds), `end` (seconds), `text` |
| `parse_vtt(vtt_path, require_chinese)` | Parses VTT → deduplicates YouTube rolling captions → merges identical adjacent lines → filters by duration and Chinese content |
| `_timestamp_to_seconds(ts)` | Converts VTT timestamp string to float seconds |
| `_clean_text(text)` | Strips HTML tags, zero-width spaces, control chars |
| `_has_chinese(text)` | Returns True if text contains CJK Unified Ideographs |

**Dependencies:** `webvtt`

---

### `clip.py`

**Purpose:** Extracts one mp4 clip per subtitle segment from the source video using ffmpeg.

| Function | Description |
|----------|-------------|
| `extract_clips(video_path, segments, output_dir, padding=0.15)` | Calls ffmpeg per segment with 150ms padding; outputs `clip_NNNN.mp4` files |

**Dependencies:** `autoanki.subtitles.Segment`

---

### `ocr.py`

**Purpose:** Extracts burned-in Chinese subtitle text from video frames using PaddleOCR.

| Symbol | Description |
|--------|-------------|
| `_ocr` | Module-level PaddleOCR instance (lang="ch") |
| `_extract_frame(video_path, timestamp, output_path)` | Uses ffmpeg to grab a single JPEG frame at a timestamp |
| `_crop_subtitle_region(image)` | Crops bottom 25% of frame where subtitles appear |
| `_is_subtitle(poly, w, h, score)` | Heuristic filter: checks Y-band (20-45% of crop), X-centering, and confidence score |
| `_ocr_chinese(image)` | Runs PaddleOCR on cropped image, filters to subtitle-like regions, returns joined text |
| `ocr_segments(video_path, segments, work_dir)` | Orchestrates OCR for all segments; caches results to `ocr_cache.json` |

**Dependencies:** `cv2`, `numpy`, `paddleocr`, `autoanki.subtitles.Segment`

---

### `ocr_preprocessing.py`

**Purpose:** Translates English subtitle text to Chinese via Claude CLI as a fallback when OCR fails.

| Symbol | Description |
|--------|-------------|
| `CHUNK_SIZE` | 150 texts per Claude CLI call |
| `translate_en_to_zh(english_texts)` | Batches English lines into numbered prompts, sends to Claude CLI, parses JSON array response |

**Dependencies:** stdlib only (`json`, `subprocess`); requires `claude` CLI on PATH

---

### `translate.py`

**Purpose:** Translates Chinese subtitle segments to English via Claude CLI.

| Symbol | Description |
|--------|-------------|
| `CHUNK_SIZE` | 150 segments per Claude CLI call |
| `translate_segments(segments)` | Batches Chinese text into numbered prompts, sends to Claude CLI, parses JSON array response |

**Dependencies:** `autoanki.subtitles.Segment`; requires `claude` CLI on PATH

---

### `cards.py`

**Purpose:** Generates an Anki .apkg deck with embedded video clips and jieba-segmented Chinese.

| Symbol | Description |
|--------|-------------|
| `AUTOANKI_MODEL` | genanki Model with 5 fields (Chinese, English, Video, SegmentedChinese, Index) and 2 templates (Listening, Reading) |
| `_deck_id_from_title(title)` | Deterministic deck ID from MD5 of title |
| `_note_guid(video_title, index)` | Deterministic note GUID for stable imports |
| `_segment_chinese(text)` | Runs jieba word segmentation, joins with " / " |
| `generate_deck(title, segments, translations, clip_paths, output_path)` | Builds deck, attaches media files, writes .apkg |

**Dependencies:** `genanki`, `jieba`, `autoanki.subtitles.Segment`

## Configuration

### CLI Usage

```
autoanki <url> [options]
```

### Flags

| Flag | Default | Effect |
|------|---------|--------|
| `url` (positional) | required | YouTube or Bilibili video URL |
| `-o`, `--output` | `<video-title>.apkg` | Output .apkg file path |
| `--work-dir` | system temp dir | Directory for intermediate files (frames, clips, cache) |
| `--keep-work-dir` | `false` | Preserve working directory after completion (for debugging) |
| `--no-translate` | `false` | Skip Chinese → English translation; English field left empty |
| `--cookies` | none | Path to cookies file for login-required videos (passed to yt-dlp) |
| `--no-ocr` | `false` | Skip OCR; translate English subs to Chinese via Claude CLI instead |

### Card Templates

Each note generates two Anki cards:

- **Listening:** Shows video clip, asks "What did they say?", reveals Chinese + segmented + English
- **Reading:** Shows Chinese text, reveals video clip + segmented + English
