---
kind: decision
title: Query mature Anki cards (ivl>=21) across all Chinese-content decks via AnkiConnect, tokenize with jieba
covers: autoanki/level/anki_import.py
---

## What was chosen

`scan_mature_morphs(deck_filter=None)` builds an AnkiConnect search query
of `prop:ivl>=21` (AnkiMorphs' mature-card convention), optionally
narrowed by a deck-name substring. It resolves cards → notes via
`cardsInfo` + `notesInfo` (500-note batches), walks every field of every
mature note, and jieba-tokenizes any field containing Han characters. The
returned `set[str]` is what the `anki` and `hybrid` profile modes union
into `known_morphs`.

## What was rejected, and why

- **A different maturity threshold.** 21 days is what AnkiMorphs uses out
  of the box and what most Chinese-learner content assumes. Configurable
  would be nice, but not before the default has a decision note attesting
  to why it was picked.
- **Only pull one designated "Chinese" deck.** A multilingual learner may
  have Chinese content spread across several decks (Core 2000, HSK, a
  drama-derived deck). Filtering out mature *English* review cards happens
  naturally because we only tokenise fields containing Han characters.
- **Only extract from a hard-coded field name like `Chinese`.** Note types
  vary (`Expression`, `Sentence`, `Front`, etc.); tokenising every
  Han-containing field is more robust and adds negligible extra work.
- **Pass the whole note-info payload into a caller-supplied filter.** Would
  couple `anki_import.py` to whatever field-selection heuristic the caller
  used; the current design is: "if it has Chinese in it, it counts."
