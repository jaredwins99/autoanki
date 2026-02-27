# autoanki

Clip Chinese TV shows/dramas into sentence-level video/audio segments, generate Anki flashcards with difficulty calibrated to the user via MorphMan (i+1 learning).

## Core Rules
- **Nothing is sacred.** Code, docs, plans — everything is subject to deletion and refactoring.
- **Prefer deletion over accumulation.** Lean repo with correct files beats bloated repo with stale files.
- **Never use MCP Linear tools** — they hang in WSL2. Use `scripts/linear.sh` or direct `curl` instead.
- **Questions to the user go through AskUserQuestion** with multiple-choice options so the user can respond with keystrokes.

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
| **Debrief** | `/project:debrief` | opus | Extracts lessons from session, updates CLAUDE.md + lessons |

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

## Architecture Decisions

- **Video source**: yt-dlp from YouTube/Bilibili (video + audio + auto-generated subs)
- **Card format**: Video clip + Chinese text + English translation
- **Translation**: Claude Code subagent translates inline during card generation (no external API)
- **NLP**: jieba for Chinese word segmentation
- **Clip strategy**: One subtitle line = one clip (simplest, upgrade to sentence merging later)
- **MVP**: Basic pipeline (video in -> Anki deck out), then layer on MorphMan i+1 filtering
- **MorphMan**: Deferred to post-MVP phase

## Tech Stack

Python, yt-dlp, ffmpeg, jieba, genanki, MorphMan (post-MVP), SRT/VTT subtitle parsing
