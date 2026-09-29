---
kind: decision
title: Parse VTT with webvtt-py; drop YouTube rolling repeats, merge consecutive identicals, gate on duration/language/junk/dedup
covers: autoanki/subtitles.py
---

## What was chosen

`parse_vtt()` walks captions via `webvtt-py`, `_clean_text` strips HTML,
zero-width spaces, control chars, and collapses whitespace, then two dedup
passes normalise YouTube auto-caption quirks: a rolling-window dedup drops
each caption's first line when it repeats the previous caption's last line
(that's how YouTube's live captioning renders), and a consecutive-identical
merge unions timestamps when the same text spans multiple captions.
Segments are then filtered on duration ≥ 0.3s, presence of Han characters
when `require_chinese=True`, absence from `_JUNK_PATTERNS` (four regexes
covering "subtitles brought by …", `Meet Yourself|eng sub|starring`, any
bracketed text, and `@handle`), and exact-string dedup by `seen_texts`.

## What was rejected, and why

- **Naive one-caption-one-segment.** YouTube's two-line rolling captions
  would produce a duplicate line for every subtitle boundary.
- **Sentence-boundary merging across captions.** Deferred: a real dialogue
  sentence sometimes spans two captions, but auto-merging by punctuation is
  brittle without ASR-aligned timing.
- **Aggressive CJK-side noise filter here.** The four English junk regexes
  are cheap and safe pre-OCR; CJK watermarks (`华策TV`), song markers (♪),
  and credit rolls need to be handled after OCR/correction has produced the
  Chinese text (see PR-4 in `~/.claude/plans/synchronous-squishing-treasure.md`).
