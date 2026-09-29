---
kind: open
title: Where does the adaptive quiz get its sentences from?
covers: autoanki/level/setup_cli.py
---

## The question

The `quiz` mode in `Profile` and `setup_cli.run` needs a corpus of sample
sentences graded by HSK band (or approximate difficulty). The quiz would
present sentences at ascending difficulty and let the user mark
known/one-new-word/too-hard until a Bayesian update over morph frequency
converges on a known-morph set.

Right now the corpus doesn't exist, so `setup_cli` prints a placeholder and
exits with code 2 when `mode == "quiz"`.

## What it blocks

- The `quiz` and `hybrid` (partially — hybrid falls back to HSK+Anki
  without the quiz refinement) modes of `autoanki setup`.
- Any personalisation beyond the coarse "which HSK band do you claim" +
  "what has your Anki matured on."

## What would settle it

Three plausible corpus sources:

1. **Ship a handcrafted set.** ~50 sentences spread across HSK 1-6, each
   tagged with its unique morphs and their HSK band. Small, deterministic,
   version-controlled. Would live in `data/quiz_sentences.yaml`.
2. **Reuse the user's already-processed autoanki output.** After the user
   has produced any deck, `observability/metrics/all_sentences.csv` (planned)
   holds every subtitle we've seen. Use that for the quiz corpus of a
   returning user.
3. **Scrape from a public corpus.** Tatoeba's Mandarin set with HSK-band
   tagging via `pyhsk` or similar. Adds a network dependency at setup time
   and complicates offline use.

Recommendation when this ships: start with (1) so the quiz is usable at
first install, add (2) as a follow-up once the observability metric exists.
