---
kind: decision
title: Persist the user's known-morph set as YAML at ~/.config/autoanki/profile.yaml, four modes converge on the same shape
covers: autoanki/level/profile.py
---

## What was chosen

`Profile` is a `@dataclass` with `source`, `known_morphs: set[str]`,
optional `hsk_baseline`, optional `anki_deck_filter`, and `updated_at`. It
persists to a YAML file whose default location follows the XDG convention:
`~/.config/autoanki/profile.yaml`, override with `AUTOANKI_PROFILE` env
var. Four source values are supported (`hsk`, `anki`, `quiz`, `hybrid`);
each mode's builder in `setup_cli.py` produces the same shape so downstream
consumers (`morph.load_known_morphs`, i+1 filter, highlight) only ever see
`known_morphs: set[str]`.

## What was rejected, and why

- **JSON persistence.** Chinese morphs render fine in JSON, but YAML is
  easier for a user to inspect and hand-edit (removing a stray morph, for
  example). The parse cost is negligible for a one-off file loaded once per
  run.
- **SQLite.** A single flat file with ~30k strings loads in ~30ms; a
  database is more moving parts and no user-visible benefit at this size.
- **Store `known_morphs` inline in every source's dataclass field.** Since
  every mode ultimately produces the same set, unifying under one field
  means downstream code doesn't branch on `source`.
- **Auto-refresh from Anki on every autoanki run.** Would tie every card
  generation to a running Anki instance and mask staleness. The wizard is
  an explicit action the user takes when their known-morphs have moved.

## Follow-up

`Profile.load()` returns None when no profile exists, and callers
(`morph.load_known_morphs`) fall back to the shipped baseline CSV. That
fallback is what every current pre-wizard user sees today; running
`autoanki setup` is what activates the personalized path.
