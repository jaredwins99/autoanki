---
kind: decision
title: Parse show+episode from video title with an ordered pattern list; nest under {deck_root}::{show}::{episode}
covers: autoanki/naming.py
---

## What was chosen

`parse_show_episode(video_title)` walks an ordered list of episode-marker
regexes and returns `(show, episode)`. Patterns run in specificity order:
`SNNENN` first (season+episode), then `EP\d+` / `Episode \d+`, then bare
`E\d+`, then Chinese `第\d+集`. Once a match is found, the episode label is
normalised to two-digit `EPNN` (or preserved as `SNNENN`), and the show
name is what appeared BEFORE the marker (everything after — episode
subtitles like "The Return", or repost tags — is dropped). Bracketed tags
(`[Eng Sub]`, `(HD)`, `【中字】`) are stripped up-front.

`build_deck_name(deck_root, show, episode)` composes
`{deck_root}::{show}::{episode}` when the episode is known and
`{deck_root}::{show}` when it isn't. Any `::` inside the components is
replaced with `-` so a stray colon can't create an unintended nesting
level.

Both are wired into `cards.generate_deck` and `ankiconnect.push_to_anki`;
the CLI parses from `dl.title` and lets `--show` / `--episode` /
`--deck-root` override.

## What was rejected, and why

- **Take everything after the episode marker as the show.** Real titles
  put the show name first and the episode subtitle after: "Meet Yourself
  S01E03 - The Return" is show "Meet Yourself", not show "The Return".
- **Regex-per-uploader (per-channel dispatch).** Would fork by uploader ID
  and maintain a table; the ordered general-pattern list gets ~7/8 of the
  observed title shapes right without any per-channel config.
- **LLM parsing.** Consistent + fast + deterministic beats a Claude call
  for a text-shape decision this simple. Escape hatch is the `--show` /
  `--episode` CLI overrides for the cases the regex misses.
- **Store show/episode on Segment.** Deck-level metadata, not
  per-segment; keeping it out of `Segment` avoids threading it through
  five stages of pipeline for one final consumer.

## Follow-up

Playlist mode (`autoanki playlist <url>`) would iterate a YouTube playlist
and group each video under the same show; the per-video episode number
parsed by this module drives the subdeck naming. Not shipped here —
tracked as PR-6b in `~/.claude/plans/synchronous-squishing-treasure.md`.
