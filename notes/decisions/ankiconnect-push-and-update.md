---
kind: decision
title: Push decks live via AnkiConnect and update the note type in place on every run
covers: autoanki/ankiconnect.py
---

## What was chosen

`push_to_anki()` targets a running Anki desktop over HTTP (v6 protocol) at
`ANKICONNECT_URL` (env-overridable, default `http://localhost:8555`). On every
run `_ensure_model()` either creates the `AutoAnki Chinese` note type or, if
it already exists, adds any fields the current template needs, then calls
`updateModelTemplates` and `updateModelStyling` so template edits reach cards
that were pushed by earlier runs. Notes dedupe per-deck by the `Chinese`
field: an existing note with the same Chinese text gets `updateNoteFields`,
otherwise `addNote` with `allowDuplicate: False`.

## What was rejected, and why

- **`.apkg` file only.** File hand-off means every code change to the template
  gets stuck behind a re-import. Live push means a template edit ships to the
  running collection the next time cards go up.
- **Hardcoded port 8765.** Collided with another local service (`hens`). The
  env var + non-default 8555 lets AnkiConnect and other tools coexist without
  a code edit per machine.
- **Recreate the model when its schema drifts.** Would orphan existing cards.
  Adding missing fields + updating templates in place keeps prior cards
  attached to the same note type; empty `am-highlighted` falls back to plain
  `{{Chinese}}` via the mustache conditional.
