---
kind: decision
title: Ship HSK 1-5 as an inline Python frozenset and expand offline with jieba into the shared CSV
covers: autoanki/hsk.py
---

## What was chosen

`_ALL_WORDS` is a literal `frozenset` of ~5,674 combined old-HSK-1-5 +
new-HSK-1-6 entries (sourced from
`github.com/drkameleon/complete-hsk-vocabulary`) embedded in the module.
`load_known_morphs()` (this file) expands that baseline by walking
`jieba.dt.FREQ`: it keeps single HSK characters, any 2-char compound built
from HSK 1-2 basic characters (no frequency gate), and any 2-4 char compound
built from HSK-known characters that also clears `freq >= 4000`. The output
is what `data/hsk1-5_known_morphs.csv` (~36.5k rows) was generated from —
runtime consumers load the CSV via `autoanki/morph.py`, not this function.

## What was rejected, and why

- **Ship a CSV without the generator.** The rules that produce the CSV
  (basic-char pair, 4000 freq threshold, HSK-char gate) are load-bearing and
  need to live in source, not just in a comment on top of a data file.
- **Regenerate morphs at every autoanki run.** Requires jieba init inside
  the pipeline and re-derives 36k morphs for no gain; the CSV cache is a
  30ms load vs. multi-second cold jieba init.
- **HSK 1-6 for both old and new.** Old HSK maxes at 5; combining old 1-5 +
  new 1-6 covers the overlap without inflating the "known" set beyond what
  a legitimate HSK-5 learner recognises.
