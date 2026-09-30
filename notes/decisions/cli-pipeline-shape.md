---
kind: decision
title: One argparse entry point wires five staged transforms, with lazy imports for the heavy ones
covers: autoanki/cli.py
---

## What was chosen

`main()` builds a single argparse parser and delegates to `_process_one(url,
args, work_dir)` per URL. The pipeline is five ordered stages: download →
parse subtitles → extract clips → resolve Chinese text (branching on sub
language: Claude translation for Chinese subs, OCR + optional Claude fill +
optional Claude correct for English subs) → optional i+1 filter → emit deck
(`.apkg` by default, AnkiConnect push under `--ankiconnect`). PaddleOCR and
AnkiConnect are imported inside their branches, not at module top, so
`--help` and `.apkg` runs don't pay the paddle load cost or require the
paddle install.

After the i+1 filter come a spoken-language filter (drop clips whose audio
isn't Mandarin; see `audio-lang-whisper-filter`) and, on the OCR path, a
Claude translation of each surviving card's Chinese. The English subtitle
line is kept only as context for OCR correction: subtitle lines split and
reorder clauses differently from the burned-in Chinese, so a cue's English
often translates the neighbouring Chinese line (我送您两张餐券 was paired
with "as you check in as present."). Filtering first means only surviving
cards are translated.

Downloads go to `$AUTOANKI_CACHE/<video-id>/download/` (default
`~/.cache/autoanki/`), never into the work dir, so cleaning up a temporary
work dir can't delete the source video.

## What was rejected, and why

- **Downloads inside the temp work dir.** That was the original layout, and
  the default cleanup deleted the episode after every run. When YouTube
  later blocked re-downloads (403 on every stream), no copy was left.

- **Subcommands (`autoanki download`, `autoanki cards`, …).** Every real run
  wants the full end-to-end; separate commands would only add glue for the
  same argparse-args shape. Reconsider when `autoanki setup` and `autoanki
  playlist` land — those are genuinely different jobs.
- **Top-level `from autoanki.ocr import ocr_segments`.** Breaks
  `--help`/`--no-ocr` when `paddlepaddle` isn't installed; the lazy import
  scopes the requirement to the OCR path.
- **Fail hard on a URL failure inside a multi-URL run.** Batch runs continue
  past a single failure so one broken video doesn't kill a night's worth of
  processing.
