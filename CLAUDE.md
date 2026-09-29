# autoanki

Clip Chinese TV shows/dramas into sentence-level video/audio segments, generate Anki flashcards with difficulty calibrated to the learner (i+1: one unknown morph per card, highlighted).

## Core Rules
- **Nothing is sacred.** Code, docs, plans — everything is subject to deletion and refactoring.
- **Prefer deletion over accumulation.** Lean repo with correct files beats bloated repo with stale files.
- **Never use MCP Linear tools** — they hang in WSL2. Use `scripts/linear.sh` or direct `curl` instead.
- **Questions to the user go through AskUserQuestion** with multiple-choice options so the user can respond with keystrokes.
- **Ask only when blocked on the user's call.** Read `notes/INDEX.md` and `legibility/docs/` first, take sensible defaults and say which, and never re-ask a settled question.
- **Never delete downloaded source media.** Videos, subtitles, and metadata under `~/.cache/autoanki/<video-id>/download/` (or anywhere else a video was fetched to) are irreplaceable inputs, not scratch: YouTube blocks re-downloads after repeated requests, and an episode deleted "because it can be re-fetched" once cost a whole session. Clean up only files you generated from them (clips, frames), and only when asked.

## 1. Validation — only empirical evidence counts

Code looking right is a hypothesis. Build in small blocks: write it, run it,
see the output, then move on. Don't stack unvalidated changes.

**What counts here**: a predicate or parser exercised on real inputs with
its output shown; a pipeline stage run on a real video or a cached work dir
(`~/.cache/autoanki/<video-id>/`); for anything that ends up on a card,
frames pulled from the clip and compared against the card text.

**What does not count**: "this should work", a diff that reads correctly,
the notes gate passing (it checks documentation, not behavior).

**Red flags**: 3+ edits without running anything; reporting a deck as done
without looking at a sampled card against its clip.

## 2. Fixed point — don't change what you weren't asked to

Existing code and prose stay as they are unless changing them is an
explicit, named decision. No renames, reformatting, "while I'm here"
cleanups, or softened wording. A secondary change is legitimate only when
the requested change requires it. Before handing off, `git diff`: every
hunk must trace to something asked for or explicitly announced.

## 3. Subjective judgment — no regex for taste

Objective checks (does the OCR text match the frame, does the sentence have
exactly one unknown morph, does the deck name parse) are code. Taste (is
this card worth studying, is this translation natural, is the filter too
strict) is not: bring it to the user with AskUserQuestion, or have a
subagent score it against a stated rubric. Noise predicates in
`autoanki/filters.py` match fixed markers (♪, 华策TV, 演唱：); they must not
grow into "does this look like dialogue" heuristics.

## Notes — the reasoning, kept honest

Full standard: `legibility/decision-notes.md`.
Gate: `python correctness/checks/check_notes.py [--evidence]`

Write a note when a future reader would otherwise re-derive or contradict
something: a decision and what it rejected, a fact about the data with the
command that shows it, an open question and what it blocks, a pointer outside
the repository. Do not write progress logs.

Every note declares the files it covers, in its frontmatter. Four things fail
the check: a covered file that no longer exists, a source file no note covers,
one file decided by two notes, and a finding whose evidence command no longer
prints its claim.

When the gate blocks you, the note or the code is wrong; fix one of them. Do
not delete a note to pass, do not narrow `notes/coverage.ini` to hide a file,
and do not edit `notes/INDEX.md`, which is generated.

When you add a directory or a language to the project, widen
`notes/coverage.ini` in the same change: code outside the scope is code the
check cannot see.

## Tenet layout

Files map 1:1 to five tenets (ported from `~/dev_template`):

- `notes/` — decision/finding/open/reference notes + `coverage.ini` + generated `INDEX.md`
- `correctness/` — `checks/`, `hooks/`, `tests/` (the note-gate lives here)
- `legibility/` — `decision-notes.md` (the note-writing standard), `docs/`
- `reproducibility/`, `observability/`, `security/` — populated as content lands

Root marker files (`CLAUDE.md`, `README.md`, `pyproject.toml`, `.pre-commit-config.yaml`, `.gitignore`) stay at repo root — they're nested under their tenet only in VS Code's file-nesting display.

## Where things are

- **Structure and data flow**: `legibility/docs/architecture.md`
- **Why each module is the way it is**: `notes/INDEX.md` → `notes/decisions/`
- **Open work**: `notes/open/` (quiz corpus, web GUI, vocab-level source)
- **History of problems and fixes**: `legibility/docs/process.md`
- **Current build plan**: `~/.claude/plans/synchronous-squishing-treasure.md`

Runtime: ffmpeg, `claude` CLI, PaddlePaddle + PaddleOCR, deno +
`yt-dlp-ejs>=0.8` (YouTube's JS challenge), AnkiConnect at
`localhost:8555` (8765 is taken by another local service).

## Agent System

Atlas (main agent) orchestrates. Delegate heavy lifting to subagents.

| Agent | Command | Model | Role |
|-------|---------|-------|------|
| **Oracle** | `/project:oracle` | opus | Deep research and analysis |
| **Explorer** | `/project:explorer` | haiku | Fast file/codebase/web discovery. Cheap and parallel-friendly |
| **Sisyphus** | `/project:sisyphus` | opus | Pure implementation. Receives plan, writes code |
| **Reviewer** | `/project:reviewer` | opus | Code review. Reads diffs, produces critique. Never writes code |
| **Prometheus** | `/project:prometheus` | opus | Deep planner. Writes plans to `plans/`. Never implements |
| **Socrates** | `/project:socrates` | opus | Asks user critical multiple-choice questions via AskUserQuestion |
| **Debrief** | `/project:debrief` | opus | Extracts lessons from session into `notes/` and CLAUDE.md |

## Orchestration Rules

1. **Parallel by default**: Launch Explorer/Oracle agents in parallel for independent research.
2. **Delegate implementation**: Hand plans to Sisyphus with explicit file paths.
3. **Review after writes**: Invoke Reviewer on changed files after implementation.
4. **Plans go to disk**: Prometheus writes all plans to `plans/` as living markdown docs.
5. **Atlas stays lean**: Orchestrate, summarize, communicate. Offload heavy lifting.
6. **Socrates for decisions**: When user input is needed, delegate to Socrates who uses AskUserQuestion with multiple-choice options.

## Agent Selection Guide

- "What does X do?" / "How should we approach Y?" → **Oracle**
- "Find all files related to X" / "What's in this codebase?" → **Explorer**
- "Implement the plan" / "Write the code for X" → **Sisyphus**
- "Review this code" / "What's wrong with this?" → **Reviewer**
- "Plan the architecture for X" / "Design the system for Y" → **Prometheus**
- "What should we decide before building X?" / "What am I missing?" → **Socrates**
- "Extract lessons from this session" → **Debrief**

## Linear Integration

- Team ID: `98283b2d-bded-4e84-89d8-46696d2cc2c3`
- Script: `scripts/linear.sh` (direct GraphQL curl, no MCP)
- States: Backlog, Todo, In Progress, Done, Canceled, Duplicate
