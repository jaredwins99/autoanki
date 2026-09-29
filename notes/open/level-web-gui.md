---
kind: open
title: Should `autoanki setup --gui` spin up a localhost web wizard alongside the TUI?
covers: autoanki/level/setup_cli.py
---

## The question

The user asked for both a TUI and a web GUI entry point into the level
wizard. TUI is done and lives in `autoanki/level/setup_cli.py`. A web GUI
would spin up a small localhost server and open a browser tab for the same
wizard, so non-terminal users can complete setup without a shell.

## What it blocks

- Nothing critical — the TUI covers 100% of functionality — but the user
  explicitly asked for both surfaces so the project can eventually be
  shared publicly with users who don't live in a terminal.

## What would settle it

Design questions to resolve before writing code:

1. **Framework.** FastHTML (single-file, minimal deps) vs. Flask
   (well-known, more surface area) vs. a static HTML page served from a
   `http.server` + POST endpoint. Given autoanki is a CLI-first project,
   the lightest option that renders a form and posts back is preferred.
2. **Where the GUI code lives.** Presumably `autoanki/level/setup_web.py`
   with `autoanki setup --gui` dispatch. Shared business logic
   (`build_hsk_profile`, `build_anki_profile`, `build_hybrid_profile`) stays
   in `setup_cli` so both frontends call the same builders.
3. **The quiz flow, when quiz mode ships.** A web quiz is much nicer than a
   terminal quiz (rendering sentences with per-morph highlights, next-button
   pacing). A blocker for `--gui` and a bonus for it.

Owner: PR-5d in `~/.claude/plans/synchronous-squishing-treasure.md`.
