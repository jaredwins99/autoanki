---
kind: decision
title: Post-correct PaddleOCR with Claude, giving it the English subtitle as ground-truth context
covers: autoanki/ocr_correct.py
---

## What was chosen

`correct_ocr()` batches OCR + English pairs into 150-line chunks, sends each
as a Claude CLI call (`claude -p … --output-format json`), and expects back
a JSON array of the same length. The rules tell Claude to keep the OCR
verbatim except to fix misread characters (traditional forms, look-alikes, a
dropped first/last character), strip non-subtitle text (watermarks, name
labels), or restore the order of two lines read out of order. It must never
add, remove or swap words to match the English, which is a loose
translation. Empty or garbage OCR is translated from the English instead. A
length mismatch on return raises rather than silently truncates.

Results are cached per episode in `work/correct_cache.json`, keyed by (OCR,
English) and by a hash of the rules. Re-runs don't re-roll text that was
already checked, and editing the rules invalidates the cache.

The earlier rule, "lightly fix OCR when it's mostly right", let Claude
rewrite correct OCR toward the English. On EP1, 3 of the 19 lines it changed
became wrong against the frame: it added 比 (158) and 是 (364), and swapped
不要了 for 不行了 (417).

## What was rejected, and why

- **Trust PaddleOCR alone.** Even at 95% hit rate, remaining garbage
  contaminates the deck; the correction pass is cheap relative to a bad
  card. Users can still opt out via `--no-ocr-correct`.
- **One giant Claude call.** Anthropic-side rate limits and long-context
  degradation make 150-line chunks safer, and let a mid-run failure be
  retryable at chunk granularity.
- **Parse Claude's output loosely.** Prompt asks for a JSON array of exact
  length, and the length check rejects any answer that isn't; a silently
  truncated array would misalign every downstream field.
