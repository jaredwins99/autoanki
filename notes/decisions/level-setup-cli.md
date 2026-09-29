---
kind: decision
title: TUI wizard dispatches on --mode; interactive prompts fall back to hsk baseline when unattended
covers: autoanki/level/setup_cli.py
---

## What was chosen

`autoanki setup` is a subcommand (dispatched from `cli.main` when
`sys.argv[1] == "setup"`) that opens `setup_cli.run()`. If `--mode` is
passed, run non-interactively; otherwise prompt through four choices
(`hsk`, `anki`, `hybrid`, `quiz`). Per mode:

- **hsk**: prompt for band 1-6, produce a profile from the shipped HSK
  frozenset in `autoanki/hsk.py`. (Per-band separation is future work; the
  current `_ALL_WORDS` is combined old-HSK-1-5 + new-HSK-1-6, so the band
  argument is currently recorded but does not further narrow the set.)
- **anki**: prompt for an optional deck-name filter, call
  `scan_mature_morphs`, save the returned morph set.
- **hybrid**: HSK baseline union Anki mature morphs — max coverage without
  discarding either signal.
- **quiz**: not yet implemented; the wizard prints a pointer and exits with
  code 2.

The profile is written to `~/.config/autoanki/profile.yaml` (or wherever
`--path` / `AUTOANKI_PROFILE` env var point). Subsequent `autoanki <url>`
runs pick it up via `morph.load_known_morphs`.

## What was rejected, and why

- **Auto-detect the "right" mode.** Would require inspecting the user's
  Anki install to decide `anki` vs `hsk`. Explicit choice is one more
  keystroke and avoids surprising a first-time user with a scan.
- **Skip the mode prompt when only one path is available.** Same reason —
  the wizard is a low-frequency, high-consequence action; a beat of
  friction is fine.
- **Make quiz mode a placeholder no-op that returns HSK baseline.** Would
  hide the incompleteness. Exit code 2 + a pointer surfaces the gap.
- **Separate `autoanki setup-hsk`, `autoanki setup-anki` binaries.** One
  wizard entry point with `--mode` keeps discovery simple; setup is a
  once-a-quarter action, not a hot path.

## Follow-up

- Web GUI (`autoanki setup --gui`) — deferred; see
  `notes/open/level-web-gui.md`.
- Quiz mode — deferred; see `notes/open/quiz-corpus.md`.
