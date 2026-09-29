---
kind: decision
title: Ship .apkg via genanki with deterministic IDs so re-imports update instead of duplicate
covers: autoanki/cards.py
---

## What was chosen

`generate_deck()` writes an `.apkg` via `genanki`. The model ID is a fixed
constant (`AUTOANKI_MODEL_ID = 1607392319`); the deck ID is derived from the
video title via md5 (`_deck_id_from_title`); each note's GUID is derived from
title + segment index (`_note_guid`). All three are deterministic, so
re-generating the deck for the same video and re-importing it into Anki
updates the existing cards instead of appending duplicates. Fields and card
templates mirror the AnkiConnect path so both output modes render identically.

## What was rejected, and why

- **Random genanki-defaulted IDs.** Every re-import would create a fresh deck
  and fresh notes, and users would end up with `AutoAnki::Meet Yourself (2)`
  clutter after every iteration.
- **Live push only.** Not everyone runs a desktop Anki with AnkiConnect
  installed; `.apkg` is the transport for mobile-first users, air-gapped
  machines, or sharing decks with friends.
- **Separate note type per video.** One shared model means any template
  improvement lands on every card across every show on next import.

## Follow-up

Template + CSS are duplicated between `cards.py` and `ankiconnect.py`. Both
paths must be edited together until the strings are lifted into a shared
constant.
