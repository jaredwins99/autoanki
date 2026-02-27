# MVP Pipeline Plan

## Goal

Take a single YouTube or Bilibili URL containing Chinese content, and produce a ready-to-import `.apkg` Anki deck where each card is one subtitle line with: a video clip, the Chinese text, and an English translation.

## Context

- No application code exists yet. The repo has only orchestration files (`CLAUDE.md`, agent commands, `scripts/linear.sh`).
- The user has Claude Code available, so translation is free via subagent invocation -- no OpenAI/DeepL API keys needed.
- Target content: Chinese YouTube videos and Bilibili videos with auto-generated or manually uploaded Chinese subtitles.
- YouTube auto-generated VTT files have a known problem: rolling captions produce duplicate/overlapping lines. We must deduplicate.
- Bilibili subtitle handling in yt-dlp is less mature than YouTube but functional for manually uploaded subs. Auto-generated Bilibili subs may or may not be available depending on the video.
- For subtitle-level clips (2-10 seconds each), we need frame-accurate cuts, which means re-encoding with ffmpeg (not stream copy).

## Approach

A single Python package `autoanki` with five focused modules and one CLI entry point. No classes where functions suffice. No async. No plugin system. Minimal abstractions -- this is an MVP.

**Key decisions:**

| Decision | Choice | Reason |
|----------|--------|--------|
| Subtitle format | VTT (convert SRT to VTT if needed) | yt-dlp default for YouTube; `webvtt-py` is the most mature Python parser |
| VTT parser | `webvtt-py` | Stable, well-documented, handles start/end timestamps natively |
| VTT dedup strategy | Custom dedup function | YouTube auto-subs produce rolling 2-line captions with overlapping timestamps. We deduplicate by checking if a caption's text is a substring of the previous caption's text, and only keep the final (longest) version of each rolling window. |
| ffmpeg invocation | `subprocess.run` calling ffmpeg directly | No need for `ffmpeg-python` wrapper -- we need exactly one command pattern and direct control over flags |
| ffmpeg cut mode | Re-encode (not `-c copy`) | Stream copy can only cut at keyframes. For 2-10 second subtitle clips, keyframe cuts produce wildly inaccurate boundaries. Re-encode with `-c:v libx264 -c:a aac` gives frame-accurate clips. |
| Video format for clips | `.mp4` (H.264 + AAC) | Universal Anki support across desktop, AnkiDroid, and AnkiMobile |
| Anki card embedding | `[sound:filename.mp4]` in field | Anki treats `[sound:...]` as media reference for both audio and video files |
| Translation | Claude Code subagent via `subprocess` calling `claude` CLI | The user runs this tool inside Claude Code sessions. We invoke `claude -p "Translate: ..."` as a subprocess. Batch translations for efficiency. |
| CLI framework | `argparse` | Zero dependencies. Adequate for MVP. |
| Deck ID generation | Hash of URL | Deterministic: re-running the same URL updates rather than duplicates the deck |

## File Structure

```
autoanki/
  __init__.py          # Version string only
  download.py          # yt-dlp download: video + subtitles
  subtitles.py         # VTT parsing, deduplication, Segment dataclass
  clip.py              # ffmpeg clip extraction
  translate.py         # Claude subagent translation
  cards.py             # genanki deck generation
  cli.py               # argparse entry point

pyproject.toml         # Project metadata + dependencies
```

No `tests/` directory in MVP. No `src/` layout. Flat package at repo root.

## Dependencies

```toml
[project]
name = "autoanki"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "yt-dlp>=2024.0",
    "webvtt-py>=0.5",
    "genanki>=0.13",
    "jieba>=0.42",
]
```

**System dependencies** (must be installed separately):
- `ffmpeg` (with libx264 and aac encoders)
- `claude` CLI (for translation subagent)

jieba is included now because we need it for word segmentation in card display (showing word boundaries helps learners), even though MorphMan difficulty scoring is post-MVP.

## Steps

### Step 1: `pyproject.toml`

Create `pyproject.toml` at repo root with the dependencies listed above. Use `[project.scripts]` to register `autoanki = "autoanki.cli:main"` as a console entry point.

**File**: `/home/godli/autoanki/pyproject.toml`

### Step 2: `autoanki/__init__.py`

Minimal init: `__version__ = "0.1.0"`

**File**: `/home/godli/autoanki/autoanki/__init__.py`

### Step 3: `autoanki/download.py` (Linear: AUT-9)

**Purpose**: Download video file and Chinese subtitle file from a URL.

**Function**: `download(url: str, output_dir: Path) -> DownloadResult`

**Returns**: A `DownloadResult` dataclass with fields:
- `video_path: Path` -- path to downloaded video file
- `subtitle_path: Path` -- path to downloaded VTT subtitle file
- `title: str` -- video title (for deck naming)

**Implementation**:

```python
from dataclasses import dataclass
from pathlib import Path
import subprocess
import json

@dataclass
class DownloadResult:
    video_path: Path
    subtitle_path: Path
    title: str

def download(url: str, output_dir: Path) -> DownloadResult:
    """Download video + Chinese subtitles from URL via yt-dlp."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Get video metadata to determine available subtitle languages
    meta_cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        url,
    ]
    meta = json.loads(subprocess.run(
        meta_cmd, capture_output=True, text=True, check=True
    ).stdout)

    title = meta.get("title", "untitled")

    # Step 2: Determine subtitle language
    # Try: zh-Hans, zh, zh-CN, zh-Hant, zh-TW (in order of preference)
    # Check both manual subs and auto subs
    sub_langs = ["zh-Hans", "zh", "zh-CN", "zh-Hant", "zh-TW"]
    available_subs = meta.get("subtitles", {})
    available_auto_subs = meta.get("automatic_captions", {})

    chosen_lang = None
    use_auto = False
    for lang in sub_langs:
        if lang in available_subs:
            chosen_lang = lang
            break
    if not chosen_lang:
        for lang in sub_langs:
            if lang in available_auto_subs:
                chosen_lang = lang
                use_auto = True
                break

    if not chosen_lang:
        raise RuntimeError(
            f"No Chinese subtitles found. "
            f"Available subs: {list(available_subs.keys())}, "
            f"Available auto subs: {list(available_auto_subs.keys())}"
        )

    # Step 3: Download video + subtitles
    output_template = str(output_dir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--sub-format", "vtt",
        "--convert-subs", "vtt",
        "--output", output_template,
        "--no-playlist",
    ]

    if use_auto:
        cmd += ["--write-auto-subs"]
    else:
        cmd += ["--write-subs"]

    cmd += ["--sub-langs", chosen_lang]
    cmd += [url]

    subprocess.run(cmd, check=True)

    # Find the downloaded files
    video_id = meta["id"]
    video_path = output_dir / f"{video_id}.mp4"
    subtitle_path = output_dir / f"{video_id}.{chosen_lang}.vtt"

    if not video_path.exists():
        # Try finding any mp4 file with the video_id
        candidates = list(output_dir.glob(f"{video_id}*.mp4"))
        if candidates:
            video_path = candidates[0]
        else:
            raise FileNotFoundError(f"Video not found at {video_path}")

    if not subtitle_path.exists():
        # Try finding any vtt file
        candidates = list(output_dir.glob(f"{video_id}*.vtt"))
        if candidates:
            subtitle_path = candidates[0]
        else:
            raise FileNotFoundError(f"Subtitles not found at {subtitle_path}")

    return DownloadResult(
        video_path=video_path,
        subtitle_path=subtitle_path,
        title=title,
    )
```

**Key design notes**:
- We fetch metadata first to determine available subtitle languages. This avoids guessing and handles the YouTube vs Bilibili subtitle availability differences.
- We prefer manual subs over auto-generated subs (manual are higher quality).
- We force mp4 output format for universal Anki compatibility.
- We convert any subtitle format to VTT so downstream parsing is always VTT.

### Step 4: `autoanki/subtitles.py` (Linear: AUT-9)

**Purpose**: Parse VTT subtitles into a list of deduplicated, timestamped segments.

**Core data structure**:

```python
from dataclasses import dataclass

@dataclass
class Segment:
    index: int        # 0-based position in the video
    start: float      # start time in seconds
    end: float        # end time in seconds
    text: str         # Chinese subtitle text (cleaned)
```

**Functions**:

1. `parse_vtt(vtt_path: Path) -> list[Segment]` -- Parse VTT, deduplicate rolling captions, return clean segments.

**Deduplication algorithm for YouTube auto-generated subs**:

YouTube auto-subs use a rolling 2-line display. The VTT looks like:

```
00:00:01.000 --> 00:00:03.000
Hello world

00:00:02.000 --> 00:00:05.000
Hello world
How are you

00:00:04.000 --> 00:00:07.000
How are you
I am fine
```

The dedup strategy:
1. Parse all captions into raw (start, end, text) tuples.
2. Strip HTML tags (YouTube VTT includes `<c>` color tags and `<lang>` tags).
3. For each caption, split into lines. If the first line of the current caption matches the last line of the previous caption, it's a rolling continuation -- drop the duplicate line.
4. Merge remaining lines into a single text per timestamp range.
5. Drop empty segments and segments that are pure punctuation.
6. Merge segments with identical text (consecutive duplicates from the rolling window).

**Additional cleaning**:
- Strip `\u200b` (zero-width space) and other Unicode control characters.
- Collapse multiple spaces/newlines into single space.
- Skip segments shorter than 0.3 seconds (likely artifacts).
- Skip segments with no Chinese characters (use a simple regex: `re.search(r'[\u4e00-\u9fff]', text)`).

**Timestamp conversion**: `webvtt-py` provides timestamps as strings like `"00:01:23.456"`. Convert to float seconds for ffmpeg.

### Step 5: `autoanki/clip.py` (Linear: AUT-9)

**Purpose**: Extract video clips from the source video, one per segment.

**Function**: `extract_clips(video_path: Path, segments: list[Segment], output_dir: Path) -> list[Path]`

**Returns**: List of paths to extracted `.mp4` clip files.

**Implementation approach**:

```python
def extract_clips(
    video_path: Path,
    segments: list[Segment],
    output_dir: Path,
    padding: float = 0.15,
) -> list[Path]:
    """Extract one mp4 clip per segment from the source video."""
    output_dir.mkdir(parents=True, exist_ok=True)
    clip_paths = []

    for seg in segments:
        clip_name = f"clip_{seg.index:04d}.mp4"
        clip_path = output_dir / clip_name

        # Add small padding around subtitle timestamps for natural feel
        start = max(0, seg.start - padding)
        end = seg.end + padding

        cmd = [
            "ffmpeg",
            "-y",                          # Overwrite without asking
            "-ss", f"{start:.3f}",         # Seek BEFORE input (fast seek)
            "-to", f"{end:.3f}",           # End time
            "-i", str(video_path),
            "-c:v", "libx264",            # Re-encode video for frame accuracy
            "-c:a", "aac",                # Re-encode audio
            "-preset", "fast",            # Encoding speed (fast is good enough)
            "-crf", "23",                 # Quality (23 is default, good balance)
            "-ac", "1",                   # Mono audio (saves space, fine for speech)
            "-ar", "44100",               # Sample rate
            "-movflags", "+faststart",    # Enable streaming in Anki player
            "-avoid_negative_ts", "make_zero",
            str(clip_path),
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        clip_paths.append(clip_path)

    return clip_paths
```

**Design notes**:
- We place `-ss` before `-i` for fast seeking (ffmpeg seeks to the nearest keyframe before the timestamp, then decodes from there). Combined with re-encoding, this gives frame-accurate output.
- `padding=0.15` seconds on each side gives a natural feel -- subtitles often appear slightly after speech starts.
- `CRF 23` with `preset fast` gives good quality at reasonable file size (~200-500KB per 5-second clip).
- Mono audio saves ~50% audio bitrate. Speech content doesn't benefit from stereo.
- `movflags +faststart` moves the moov atom to the beginning of the file so Anki can start playback immediately.

**Performance concern**: For a 20-minute video with ~200 subtitle lines, this will take 3-10 minutes depending on hardware. Each clip requires seeking + re-encoding. This is acceptable for MVP. Future optimization: batch all clips in a single ffmpeg command using the `segment` muxer or parallel processing.

### Step 6: `autoanki/translate.py` (Linear: AUT-10)

**Purpose**: Translate Chinese subtitle text to English using Claude as a subagent.

**Function**: `translate_segments(segments: list[Segment]) -> list[str]`

**Returns**: List of English translations, one per segment, in the same order.

**Implementation**:

```python
import subprocess
import json

def translate_segments(segments: list[Segment]) -> list[str]:
    """Translate Chinese segments to English using Claude CLI."""

    # Batch all segments into one prompt for efficiency
    # Claude handles large prompts well, and one call is better than 200
    numbered_lines = "\n".join(
        f"{i}: {seg.text}" for i, seg in enumerate(segments)
    )

    prompt = f"""Translate each numbered Chinese line to natural English.
Return ONLY a JSON array of strings, where index i is the translation of line i.
Do not add explanations. Do not change the numbering. Do not skip any lines.

{numbered_lines}"""

    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )

    # Parse the response -- Claude returns JSON with a "result" field
    response = json.loads(result.stdout)
    content = response.get("result", result.stdout)

    # Extract the JSON array from the response
    # Handle case where Claude wraps it in markdown code blocks
    if isinstance(content, str):
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        translations = json.loads(content)
    else:
        translations = content

    if len(translations) != len(segments):
        raise ValueError(
            f"Translation count mismatch: got {len(translations)}, "
            f"expected {len(segments)}"
        )

    return translations
```

**Design notes**:
- **Batch, don't loop**: One Claude call for all segments is dramatically faster than one call per segment. A 20-minute video has ~200 lines -- one batch call takes ~10 seconds vs ~200 calls taking minutes.
- **JSON output**: We ask for a JSON array so parsing is deterministic. No regex extraction needed.
- **Chunking for long videos**: If a video has more than ~300 segments, split into chunks of 200 and make multiple calls. Add this as a TODO in the code but don't implement for MVP (most videos will have <300 subtitle lines).
- **Error handling**: If the JSON parse fails or the count mismatches, raise an error. The user can re-run. No retry logic in MVP.
- **`claude` CLI**: We use `claude -p` (prompt mode) which returns the response and exits. The `--output-format json` flag returns structured output.

**Fallback for running outside Claude Code**: If `claude` CLI is not available, the translate function should catch `FileNotFoundError` and raise a clear error message telling the user to either install the Claude CLI or provide pre-translated subtitles.

### Step 7: `autoanki/cards.py` (Linear: AUT-11)

**Purpose**: Generate an `.apkg` Anki deck from segments, translations, and video clips.

**Function**: `generate_deck(title: str, segments: list[Segment], translations: list[str], clip_paths: list[Path], output_path: Path) -> Path`

**Implementation**:

```python
import hashlib
import genanki

# Deterministic model ID (stable across runs)
AUTOANKI_MODEL_ID = 1607392319  # Random but fixed

AUTOANKI_MODEL = genanki.Model(
    AUTOANKI_MODEL_ID,
    "AutoAnki Chinese",
    fields=[
        {"name": "Chinese"},
        {"name": "English"},
        {"name": "Video"},
        {"name": "SegmentedChinese"},  # jieba word-segmented version
        {"name": "Index"},             # Position in video (for sorting)
    ],
    templates=[
        {
            "name": "Listening",
            "qfmt": "{{Video}}<br><br>What did they say?",
            "afmt": '{{FrontSide}}<hr id="answer">'
                    "<p>{{Chinese}}</p>"
                    "<p style='color: #666; font-size: 0.9em;'>{{SegmentedChinese}}</p>"
                    "<p style='color: #888;'>{{English}}</p>",
        },
        {
            "name": "Reading",
            "qfmt": "<p style='font-size: 1.5em;'>{{Chinese}}</p>",
            "afmt": '{{FrontSide}}<hr id="answer">'
                    "{{Video}}"
                    "<p style='color: #666; font-size: 0.9em;'>{{SegmentedChinese}}</p>"
                    "<p style='color: #888;'>{{English}}</p>",
        },
    ],
    css="""
    .card {
        font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;
        font-size: 20px;
        text-align: center;
        color: #333;
        background-color: #fff;
    }
    """,
)

def _deck_id_from_title(title: str) -> int:
    """Generate deterministic deck ID from title."""
    return int(hashlib.md5(title.encode()).hexdigest()[:8], 16)

def _segment_chinese(text: str) -> str:
    """Word-segment Chinese text using jieba."""
    import jieba
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
        clip_filename = clip_path.name
        media_files.append(str(clip_path))

        note = genanki.Note(
            model=AUTOANKI_MODEL,
            fields=[
                seg.text,                          # Chinese
                translation,                       # English
                f"[sound:{clip_filename}]",        # Video
                _segment_chinese(seg.text),        # SegmentedChinese
                str(seg.index),                    # Index
            ],
            sort_field=str(seg.index),
        )
        deck.add_note(note)

    package = genanki.Package(deck)
    package.media_files = media_files

    output_path.parent.mkdir(parents=True, exist_ok=True)
    package.write_to_file(str(output_path))

    return output_path
```

**Card design decisions**:
- **Two card types**: "Listening" (hear video, produce meaning) and "Reading" (see Chinese text, understand meaning). These are the two most useful directions for comprehension-focused learners.
- **SegmentedChinese field**: Uses jieba to insert ` / ` between words. This helps learners parse unfamiliar character sequences into words. Shown on the answer side in a muted color.
- **No production cards** (English -> Chinese): Production is much harder and not useful at the comprehension stage this tool targets.
- **`[sound:clip.mp4]`**: Anki uses the same `[sound:...]` syntax for both audio and video. When it encounters an mp4, it renders a video player.
- **Deck naming**: `AutoAnki::title` uses Anki's `::` separator to create a subdeck under an "AutoAnki" parent deck. This keeps auto-generated decks organized.
- **Deterministic IDs**: Both deck ID and model ID are deterministic so re-running the same video doesn't create duplicate decks/models in Anki.

### Step 8: `autoanki/cli.py` (Linear: AUT-13)

**Purpose**: Tie everything together with a simple CLI.

```python
import argparse
import tempfile
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        prog="autoanki",
        description="Generate Anki flashcards from Chinese video content.",
    )
    parser.add_argument("url", help="YouTube or Bilibili video URL")
    parser.add_argument(
        "-o", "--output",
        help="Output .apkg file path (default: <video-title>.apkg)",
    )
    parser.add_argument(
        "--work-dir",
        help="Working directory for intermediate files (default: temp dir)",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Don't delete working directory after completion",
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Skip translation (English field will be empty)",
    )

    args = parser.parse_args()

    # Set up working directory
    if args.work_dir:
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        tmp = tempfile.mkdtemp(prefix="autoanki_")
        work_dir = Path(tmp)
        cleanup = not args.keep_work_dir

    try:
        from autoanki.download import download
        from autoanki.subtitles import parse_vtt
        from autoanki.clip import extract_clips
        from autoanki.translate import translate_segments
        from autoanki.cards import generate_deck

        # Stage 1: Download
        print(f"Downloading video and subtitles...")
        dl = download(args.url, work_dir / "download")
        print(f"  Video: {dl.video_path.name}")
        print(f"  Subs:  {dl.subtitle_path.name}")
        print(f"  Title: {dl.title}")

        # Stage 2: Parse subtitles
        print(f"Parsing subtitles...")
        segments = parse_vtt(dl.subtitle_path)
        print(f"  Found {len(segments)} segments")

        if not segments:
            print("No valid subtitle segments found. Exiting.")
            return

        # Stage 3: Extract clips
        print(f"Extracting video clips...")
        clip_dir = work_dir / "clips"
        clip_paths = extract_clips(dl.video_path, segments, clip_dir)
        print(f"  Extracted {len(clip_paths)} clips")

        # Stage 4: Translate
        if args.no_translate:
            translations = ["" for _ in segments]
            print("Skipping translation (--no-translate)")
        else:
            print(f"Translating {len(segments)} segments...")
            translations = translate_segments(segments)
            print(f"  Translated {len(translations)} segments")

        # Stage 5: Generate deck
        output_path = Path(args.output) if args.output else Path(f"{dl.title}.apkg")
        print(f"Generating Anki deck...")
        result = generate_deck(dl.title, segments, translations, clip_paths, output_path)
        print(f"  Deck saved to: {result}")

        print(f"\nDone! Import {result} into Anki.")

    finally:
        if cleanup:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
```

**CLI flags**:
- `url` (positional, required): The video URL.
- `-o / --output`: Output path. Defaults to `<video-title>.apkg` in the current directory.
- `--work-dir`: Persistent working directory. Useful for debugging -- you can inspect intermediate files.
- `--keep-work-dir`: Keep temp files after completion. Useful for debugging.
- `--no-translate`: Skip the Claude translation step. Produces cards with empty English fields. Useful if the user wants to add translations manually or doesn't have the Claude CLI.

## Open Questions

1. **Bilibili cookies**: Some Bilibili videos require login. yt-dlp supports `--cookies-from-browser` and `--cookies` flags. Should we expose a `--cookies` flag in the CLI? **Recommendation**: Yes, add `--cookies` as an optional flag that passes through to yt-dlp. Low effort, high value. Implement in MVP.

2. **Very long videos**: A 45-minute drama episode might produce 400+ subtitle lines and 400+ clips. The ffmpeg extraction step could take 20+ minutes. **Recommendation**: Add a progress bar (just print `clip N/M`) in MVP. Parallel ffmpeg is a post-MVP optimization.

3. **Translation chunk size**: If a video has 500+ segments, a single Claude prompt may be too long or produce errors. **Recommendation**: Chunk at 150 segments per call in the initial implementation. Simple, safe.

4. **Subtitle language detection for Bilibili**: Bilibili subtitle language codes may differ from YouTube's. **Recommendation**: The metadata-first approach in `download.py` handles this -- we check what's actually available rather than guessing.

5. **genanki note GUIDs**: genanki auto-generates GUIDs for notes. If the user re-runs the same video, they'll get duplicate notes. **Recommendation**: Override `guid` on each note using a hash of `(video_id, segment_index)`. This makes re-runs idempotent. Implement in MVP.

## Definition of Done

The MVP is done when:

1. Running `autoanki "https://www.youtube.com/watch?v=SOME_CHINESE_VIDEO"` produces a valid `.apkg` file.
2. The `.apkg` can be imported into Anki desktop.
3. Each card has:
   - A playable video clip on the front (Listening card) or answer (Reading card)
   - Chinese text
   - jieba-segmented Chinese text (on answer side)
   - English translation (or empty if `--no-translate`)
4. Video clips start and end at approximately the right subtitle timestamps (within ~0.2s).
5. No duplicate/garbage subtitle lines from YouTube auto-sub rolling captions.
6. The tool handles at least one YouTube URL and one Bilibili URL successfully.
7. Clear error messages when: ffmpeg not installed, yt-dlp not installed, claude CLI not available, no Chinese subtitles found.

## Execution Order for Sisyphus

Implement in this order (each step is independently testable):

1. `pyproject.toml` + `autoanki/__init__.py`
2. `autoanki/subtitles.py` -- can be tested with a sample VTT file
3. `autoanki/download.py` -- can be tested with a real URL
4. `autoanki/clip.py` -- can be tested with a video + segments
5. `autoanki/translate.py` -- can be tested with hardcoded segments
6. `autoanki/cards.py` -- can be tested with dummy data
7. `autoanki/cli.py` -- integration, ties it all together

## Linear Issue Mapping

| File | Linear Issue |
|------|-------------|
| `download.py`, `subtitles.py`, `clip.py` | AUT-9 (Extract subtitles and segment clips) |
| `translate.py`, jieba segmentation in `cards.py` | AUT-10 (Chinese NLP pipeline) |
| `cards.py` | AUT-11 (Generate Anki cards with media) |
| `cli.py` | AUT-13 (End-to-end CLI pipeline) |
| (post-MVP) | AUT-12 (MorphMan integration) |
