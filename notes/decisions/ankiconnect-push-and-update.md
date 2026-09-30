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
otherwise `addNote` with `allowDuplicate: False`. After the push, notes in
the deck that this run didn't add or update are deleted, so the deck mirrors
the latest run of its episode. Cards that an improved filter now rejects
(names, transparent compounds) leave the deck rather than lingering. The
cleanup query is `"deck:X" -"deck:X::*"`, because Anki's `deck:X` also
matches subdecks: a show-level push (a video with no parsed episode) would
otherwise delete every episode deck under the show. The push then calls
AnkiConnect's `sync`, since desktop Anki only syncs on open/close, so
AnkiWeb, and through it the user's phone and laptop, gets the cards without
anyone at the desktop. A failed sync only prints a warning.

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
