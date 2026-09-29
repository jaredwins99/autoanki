# autoanki: Process Playbook

How we built a "video URL in → Anki deck out" pipeline, what went wrong, what worked, and how to systematize it for new languages, new video sources, and better quality.

---

## 1. The Build Process (What We Did)

### Phase 1: Scope & Decisions
**Time:** ~30 minutes of back-and-forth

Before writing any code, we resolved 8 key decisions via structured multiple-choice questions:

| Decision | Options Considered | Chose | Why |
|----------|-------------------|-------|-----|
| Video source | yt-dlp / browser extension / manual | yt-dlp | Scriptable, handles YouTube + Bilibili |
| Card format | Audio-only / Video clip + text / Screenshot | Video clip + text + translation | Most context for language learning |
| Translation engine | Claude API / Claude CLI subagent / Google | Claude CLI subagent | No API key management, already available |
| MVP scope | Full pipeline / MorphMan first | Basic pipeline first | Ship something usable, layer difficulty later |
| NLP | jieba / pkuseg / spaCy | jieba | Simplest, good enough for segmentation |
| Clip strategy | One sub line = one clip / Sentence merging | One line = one clip | Simplest. Upgrade later |
| Subtitle source | Auto-generated / Manual / Both | Both (prefer manual Chinese, fall back to English + OCR) | Maximize coverage |
| Translation direction | Chinese→English / English→Chinese / Both | Both depending on sub language | Handles any video |

**Lesson:** Resolving these upfront prevented backtracking. Every question had 2-4 concrete options, not open-ended discussion.

### Phase 2: Plan
**Time:** ~15 minutes

Wrote `plans/mvp-pipeline.md` with explicit:
- File names and their responsibilities
- Data flow between stages
- Interface contracts (what each function takes and returns)

**Lesson:** Naming files and functions in the plan meant implementation was mechanical — no design decisions left.

### Phase 3: Build
**Time:** ~1 hour

Built 7 modules in dependency order:
1. `subtitles.py` — VTT parsing (no external deps beyond webvtt)
2. `download.py` — yt-dlp wrapper
3. `clip.py` — ffmpeg clip extraction
4. `translate.py` — Claude CLI Chinese→English
5. `ocr.py` — Frame extraction + OCR
6. `cards.py` — genanki deck generation
7. `cli.py` — Wires it all together

**Lesson:** Building leaf modules first (no internal deps) then composing them made each piece independently testable.

### Phase 4: Debug & Iterate
**Time:** ~3 hours (the bulk of the work)

This is where all the real problems lived. See Section 2.

---

## 2. Problems Encountered & Solutions

### Problem 1: No Chinese Subtitles Available
**Symptom:** Video has Chinese audio but YouTube classified it as English. No Chinese subs downloaded.

**Root cause:** YouTube's auto-captions are based on detected language. Chinese dramas with professional English subs get classified as "English content."

**Solution:** Download English subs for timestamps, OCR the video frames for Chinese text. The pipeline now branches:
- Chinese subs available → translate to English
- English subs only → OCR frames for Chinese, use English as translation

**Systematize:** Always download both Chinese and English subs. The `sub_langs` list in `download.py` covers: `zh-Hans, zh, zh-CN, zh-Hant, zh-TW, en`. Prefer Chinese, fall back to English. Never include YouTube's auto-translated codes (`zh-Hans-en`): they are machine translations of the English track, and taking one as Chinese skips OCR of the real burned-in subs.

### Problem 2: YouTube Rate Limiting (429)
**Symptom:** Multiple yt-dlp calls (metadata probe + download + subs) triggered 429 errors.

**Root cause:** Each yt-dlp invocation makes multiple HTTP requests. Running 3+ calls in sequence trips YouTube's rate limiter.

**Solution:** Consolidated to a single yt-dlp call that downloads video + all sub variants at once. Added `--sleep-requests 1` and `--ignore-errors`.

**Systematize:** Never make multiple yt-dlp calls per video. One call, get everything. Use `--print-json` to get metadata from the same call.

### Problem 3: Tesseract OCR Quality
**Symptom:** 37% hit rate. Garbled output like `亻龙好` instead of `你好`.

**Root cause:** Tesseract is not competitive for Chinese text recognition, especially on video frames with varying backgrounds, fonts, and compression artifacts.

**Solution:** Replaced with PaddleOCR (PP-OCRv5). Hit rate jumped to 95%+ with 0.99+ confidence scores.

**Systematize:** For any CJK OCR task, default to PaddleOCR. Tesseract is only viable for clean, high-contrast, single-font documents.

### Problem 4: OCR Reads Background Text
**Symptom:** PaddleOCR picks up signs, documents, character name labels, watermarks — not just subtitles.

**Root cause:** PaddleOCR correctly reads ALL text in the frame. We only want the subtitle line.

**Solution evolved through 3 iterations:**

1. **Aspect ratio filter (W:H > 3.0 + width > 15%)** — Too aggressive. Dropped short subtitles like `谢谢`, `爸呢` (2-3 characters are nearly square).

2. **Relaxed aspect ratio (W:H > 2.0)** — Better, but still dropped 2-char subs (W:H ≈ 1.8) and let through some background text that happened to be wide.

3. **Y-band filter (cy 20%-45% of crop height)** — The winner. Burned-in subtitles sit at a rock-solid cy ≈ 0.32 in the bottom-25% crop. Background text appears at different Y positions. This filter keeps ALL subtitle lengths while rejecting almost all noise.

**Systematize:** For any video OCR task:
1. Crop to the subtitle region first (bottom 25% of frame)
2. Use Y-band positioning as the primary filter — subtitles are rendered at a fixed vertical position by the video encoder
3. Use X-centering as secondary filter (middle 80% of width)
4. Confidence threshold (> 0.5) as baseline
5. Test on a sample of ~15 frames covering short subs, long subs, and frames with background text before running full batch

### Problem 5: OCR Is Slow
**Symptom:** 655 frames × ~1 second each = 10+ minutes per run. Re-running the pipeline repeats all OCR.

**Solution:** Cache OCR results to `ocr_cache.json` keyed by frame number. Re-runs skip cached frames.

**Systematize:** Any expensive per-frame operation should cache results. Key by frame identifier (segment index), store in work directory.

---

## 3. Quality Metrics

| Metric | Value | How to Measure |
|--------|-------|----------------|
| OCR hit rate | 95% (623/655) | `sum(1 for t in texts if t) / len(texts)` |
| OCR accuracy | ~98% on hits | Manual spot-check of 15 random samples |
| Empty frames | 32/655 | Mostly intro (0-2), transitions, end credits (610-624) |
| Noise frames | ~5/655 | Background text that passes filter (hotel form in frame 12, watermarks) |
| Processing time (first run) | ~12 min | Frame extraction + OCR for 655 segments |
| Processing time (cached) | ~5 sec | Cache lookup only |

---

## 4. Extending to New Videos

### Same language (Chinese drama with English subs)
Just run it: `autoanki <url>`. The pipeline handles everything.

### Chinese drama with Chinese subs
Simpler path — no OCR needed. Pipeline auto-detects Chinese subs and translates to English.

### Different subtitle position
The Y-band filter (`cy 20%-45%`) is calibrated for standard Chinese drama subtitle positioning. If a different video source places subtitles differently:
1. Extract 5-10 frames: `ffmpeg -ss <time> -i video.mp4 -vframes 1 frame.jpg`
2. Run PaddleOCR on the crop and check `cy` values
3. Adjust the band in `_is_subtitle()` if needed

### Different language (Japanese, Korean)
1. Change PaddleOCR `lang` parameter (`"japan"`, `"korean"`)
2. Update `_has_chinese()` regex in `subtitles.py` to match the target script
3. Update translation prompts in `translate.py` / `ocr_preprocessing.py`
4. jieba won't work — swap for language-appropriate segmentation (MeCab for Japanese, KoNLPy for Korean)

### Different video source (Bilibili, local file)
- Bilibili: yt-dlp supports it natively. Same pipeline.
- Local file: Need to add a `--local` flag that skips download and takes a video + subtitle path directly.

---

## 5. Known Issues & Improvements

### Bugs
- **`--cookies` flag is parsed but never passed to yt-dlp.** Wire it through in `download.py`.
- **Frame 12-type noise:** When background text (signs, forms) physically overlaps the subtitle Y-band, it passes the filter. Could add a font-size heuristic (subtitle text is larger than background text at that distance).
- **End credits OCR:** Frames 632-654 produce `有风小`, `风小` — OCR reading partial title card text. Could detect and skip credits by checking for repeated identical OCR across consecutive frames.

### Performance
- **Parallel OCR:** `ocr_segments` processes frames sequentially. PaddleOCR supports batch prediction — could process N frames at once.
- **Skip frame extraction for cached:** Currently extracts the JPEG even for cached frames. Should check cache before calling ffmpeg.
- **Smaller clips:** CRF 23 produces ~350KB/clip. CRF 28 would halve size with minimal quality loss for Anki.

### Quality
- **Multi-frame voting:** For borderline OCR, extract 3 frames per segment (25%, 50%, 75% timestamp) and pick the one with highest confidence.
- **Claude post-processing:** Send OCR results + English subs to Claude for correction. OCR errors like `吉须到前名办理登记` could be fixed with context.
- **Sentence merging:** Currently one subtitle line = one card. Some sentences span 2-3 lines. Merge consecutive segments that form a complete sentence.

### Features (Post-MVP)
- **MorphMan integration:** Sort cards by i+1 difficulty. Requires exporting word lists from existing Anki decks.
- **Frequency lists:** Tag each card with word frequency data. HSK levels for Chinese.
- **Audio-only cards:** Extract just the audio for listening practice without video (smaller deck size).

---

## 6. Repeatable Process Template

For building any "media → flashcards" pipeline:

```
1. SCOPE (30 min)
   - What's the input? (URL, local file, API)
   - What's on the card? (text, audio, video, image)
   - What extraction is needed? (OCR, ASR, subtitle parsing)
   - What translation/NLP is needed?
   - Resolve all decisions before writing code.

2. PLAN (15 min)
   - Name every file and function.
   - Define data flow: input → stage 1 → stage 2 → ... → output
   - Define interfaces between stages (dataclasses, function signatures).
   - Write plan to disk.

3. BUILD (1-2 hours)
   - Build leaf modules first (no internal deps).
   - Build composition layer last (CLI).
   - Test each module independently before integration.

4. DEBUG (2-4 hours, the real work)
   - Run on a real video immediately. Don't wait for "perfect."
   - Problems will be in: download (rate limits, format),
     extraction (OCR quality, noise), and edge cases (credits,
     transitions, overlapping text).
   - Iterate on the worst bottleneck first.
   - Cache expensive operations.

5. VALIDATE
   - Random sample of 15+ cards.
   - Check: text accuracy, translation quality, clip timing.
   - Measure hit rate and noise rate.

6. DOCUMENT & CHECKPOINT
   - Architecture doc (tree structure, module reference).
   - Process doc (this document — what broke, what worked).
   - Git checkpoint before and after refactoring.
```

---

## 7. Tool & Dependency Notes

| Tool | Version | Purpose | Gotchas |
|------|---------|---------|---------|
| yt-dlp | latest | Video + subtitle download | Needs `node` JS runtime. Use `--sleep-requests 1`. Single call per video. |
| ffmpeg | system | Frame extraction, clip cutting | Use `-ss` before `-i` for fast seeking. |
| PaddleOCR | PP-OCRv5 | Chinese text recognition | First run downloads ~1GB models. Disable doc orientation/unwarping for speed. |
| Claude CLI | latest | Translation (both directions) | Use `--output-format json`. Chunk at 150 items max. |
| genanki | latest | .apkg generation | Deterministic IDs prevent duplicate decks on re-import. |
| jieba | latest | Chinese word segmentation | Just works. No config needed. |
| webvtt-py | latest | VTT subtitle parsing | YouTube auto-subs need deduplication (rolling 2-line captions). |
