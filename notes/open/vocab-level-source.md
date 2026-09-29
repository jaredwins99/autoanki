---
kind: open
title: How does autoanki learn a user's actual vocabulary level?
covers: autoanki/morph.py
---

## The question

`autoanki/morph.py` loads a single shipped CSV
(`data/hsk1-5_known_morphs.csv`, 36,586 morphs) as *the* known set for every
install. That is right for exactly one user profile: HSK 5-ish, no personal
Anki history. For every other user the i+1 filter and the highlight either
under-mark (advanced users see everything as "new") or over-mark (beginners
see nothing highlighted because the CSV is broader than their knowledge).

## What it blocks

- Multi-user use of the repo. Nobody's level is the shipped CSV's level.
- Correct i+1 behaviour, which by construction depends on knowing the user's
  actual known set.
- Meaningful highlight quality: the whole point of the yellow span is
  "this is the new word for *you*."

## What would settle it

A `Profile` type with `known_morphs: set[str]`, populated by one of:

1. **HSK bootstrap.** User picks HSK 1–6; profile is the union of those
   bands from the shipped CSV.
2. **AnkiConnect scan.** Pull cards with `prop:ivl>=21` (AnkiMorphs mature
   threshold) across all Chinese decks, jieba-tokenize the Chinese fields,
   union the morphs.
3. **Adaptive quiz.** Present ~30–50 sentences from a corpus straddling HSK
   band boundaries; user marks known/one-new-word/too-hard; Bayesian narrow
   on morph frequency.
4. **Hybrid.** Baseline from (1), subtract morphs missed in (3), add morphs
   from (2).

`autoanki/morph.py` already accepts a caller-supplied `known: set[str]` — the
lift is upstream: a `Profile` module (`autoanki/level/`), a `Profile`-aware
`cli.py`, and a `~/.config/autoanki/profile.yaml` persist location.

Owner: this ships as PR-5 per `~/.claude/plans/synchronous-squishing-treasure.md`.
