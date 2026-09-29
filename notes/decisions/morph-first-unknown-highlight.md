---
kind: decision
title: Highlight only the first unknown morph per sentence, at generation time, against the shipped HSK CSV
covers: autoanki/morph.py
---

## What was chosen

`highlight_first_unknown()` tokenizes a sentence with jieba, walks tokens in
order, and wraps the *first* token that (a) contains a Han character and (b) is
absent from the loaded known-morph set in `<span morph-status="unknown">…</span>`.
The default known-morph set comes from `data/hsk1-5_known_morphs.csv` at
package generation time. `unknown_morphs()` returns every distinct unknown
morph in order and is used by the `--i-plus-one` filter in `cli.py` to keep
only sentences with exactly one unknown token.

## What was rejected, and why

- **Highlight every unknown morph.** AnkiMorphs' focus-morph convention is
  one target per card; multi-highlight defeats the "one new thing to learn"
  framing. Users already exposed to n+2 material do not benefit from a card
  that flags four unknowns.
- **Compute highlights at review time via AnkiMorphs Recalc.** Requires every
  user to install and configure a plugin. Ships the deck as a plain, working
  artifact that renders yellow immediately after import. AnkiMorphs still
  works on top and, when run, overwrites `am-highlighted` with a personalized
  version — the two modes coexist.
- **Fold "known" state into a per-user file at run time.** Deferred to the
  vocab-level subsystem (see `notes/open/vocab-level-source.md`). Until that
  ships, one shipped baseline CSV is what every install sees.

## The morph-status attribute vs. a class name

`morph-status="unknown"` is chosen to match AnkiMorphs' recent versions,
which key their CSS off this attribute. The `.am-unknown` class name (used by
older AnkiMorphs) is styled by the same rule as a fallback. Both live in the
CSS block in `autoanki/cards.py` and `autoanki/ankiconnect.py`.
