---
kind: decision
title: Split noise detection into six named predicates across two insertion points, drop by default
covers: autoanki/filters.py
---

## What was chosen

`autoanki/filters.py` exposes six `is_*` predicates plus a `repeated_texts`
counter, composed by two entry functions:

- `is_noise_pre_ocr(text)` — English-side, called from `subtitles.parse_vtt`
  under the `drop_noise=True` default. Covers `is_bracketed`,
  `is_song_lyric_marker`, `is_credit_marker`.
- `is_noise_post_ocr(text, repeated)` — CJK-side, called from
  `cli._process_one` between OCR/correct and the i+1 filter. Covers
  `is_cjk_watermark`, `is_cjk_song_marker`, `is_cjk_stage_direction`, plus a
  cross-segment `repeated-static` check that flags any Chinese text
  appearing ≥3 times across the batch as a static overlay.

The pipeline drops noise by default. `--keep-noise` disables both passes for
users who want the raw stream.

Each predicate returns `(is_noise, reason)` where `reason` is a short
kebab-case tag; the CLI logs a per-run breakdown like
`noise filter: dropped 12/850 (cjk-watermark=8, repeated-static=3, cjk-song-marker=1)`.

## What was rejected, and why

- **One monolithic `is_junk()` extended.** The existing regex in
  `subtitles.py` catches four things and reports none of them; distinct
  named predicates let the CLI print which category is dropping cards, and
  let a future user narrow-drop just one class with a flag.
- **Filter on both sides using the same predicates.** English watermarks
  (`@HuaceTV`) and CJK watermarks (`华策TV`) are different regexes on
  different alphabets at different pipeline stages — sharing the function
  name would force one signature to handle both.
- **Threshold-configurable predicates.** `repeated_texts(threshold=3)` is
  the only tunable knob for now; the CJK regexes hard-code well-known
  broadcaster labels because a config surface for "add a watermark string"
  is premature. Adding a channel = editing the regex + updating this note.
- **Cross-frame OCR repetition detected inside `ocr.py`.** Would require
  passing the whole batch to a single-frame function; the natural place is
  after OCR and correction finish, where the final Chinese text list exists.

## Follow-up

`--noise-report` writing `observability/metrics/noise_dropped.csv` per run
is planned (see `~/.claude/plans/synchronous-squishing-treasure.md` §D). Not
in this change because `observability/` doesn't have any other consumers yet.
