---
kind: decision
title: PaddleOCR PP-OCRv5 with a bottom-25% crop + Y-band 20-45% + X-center 10-90% + confidence 0.5 filter
covers: autoanki/ocr.py
---

## What was chosen

`_ocr` is a module-level `PaddleOCR(lang="ch")` with doc orientation and
unwarping disabled for speed. Per frame: extract at segment midpoint (ffmpeg
`-ss` + `-vframes 1`), crop the bottom 25% (`_crop_subtitle_region`), run
PaddleOCR, keep detections that clear `_is_subtitle` — `score ≥ 0.5`, cy
between 20% and 45% of the crop height (i.e. cy ≈ 0.32 within the crop is
where burned-in subs sit), cx within the middle 80%. Kept detections are
sorted by cy and concatenated. Results are cached to `ocr_cache.json` keyed
by segment index; frame extraction is thread-pooled across 4 workers, but
OCR runs sequentially because PaddleOCR isn't re-entrant.

## What was rejected, and why

- **Tesseract.** ~37% hit rate on Chinese TV subs vs. 95% with PaddleOCR
  (`legibility/docs/process.md` §2 Problem 3). Tesseract handles clean
  single-font documents; it doesn't handle broadcast subtitle rendering.
- **Aspect-ratio filter.** Iterated to `W:H > 3.0` then `> 2.0`; dropped
  legitimate 2-char subs like `谢谢` (nearly square) and let some wide
  background text through. The Y-band filter came out of that failure
  (`legibility/docs/process.md` §2 Problem 4).
- **OCR the whole frame.** PaddleOCR reads every text region — signs,
  document forms, watermarks. Cropping first cuts the input, then the Y-band
  filter drops the remaining non-subtitle detections.
