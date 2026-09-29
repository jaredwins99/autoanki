---
kind: decision
title: Post-correct PaddleOCR with Claude, giving it the English subtitle as ground-truth context
covers: autoanki/ocr_correct.py
---

## What was chosen

`correct_ocr()` batches OCR + English pairs into 150-line chunks, sends each
as a Claude CLI call (`claude -p … --output-format json`), and expects back
a JSON array of the same length. The prompt instructs Claude to lightly fix
OCR when it's mostly right, but to translate the English directly to
colloquial spoken Chinese when the OCR is empty, garbled, or contains only
watermarks like `WX` or character-name labels. A length mismatch on return
raises rather than silently truncates.

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
