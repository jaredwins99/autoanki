---
kind: decision
title: When OCR isn't running, translate the English subtitle to spoken Chinese via Claude CLI
covers: autoanki/ocr_preprocessing.py
---

## What was chosen

`translate_en_to_zh()` is the OCR-off fallback: when `--no-ocr` is passed or
when OCR has >50% empty results (`cli.py` L70-77 kicks off a fill run), each
English line is batched (150 per Claude call) and translated to
conversational spoken Chinese. Same call shape as `translate.py` and
`ocr_correct.py`: `claude -p … --output-format json`, expects a JSON array,
enforces exact length on return, raises on mismatch.

## What was rejected, and why

- **Skip the Chinese side entirely when OCR fails.** Would leave cards with
  an English-only front, defeating the point of a Chinese Anki deck.
- **Use a translation API (DeepL, Google).** Adds a second API key and
  billing surface for a project whose only external service is already
  Claude; the quality gap for TV dialogue isn't wide enough to justify it.
- **One shared translation function across `translate.py`,
  `ocr_correct.py`, and this file.** Prompts differ meaningfully (direction,
  correction vs. pure translation, "spoken" vs. "natural"); collapsing them
  would leak concerns.
