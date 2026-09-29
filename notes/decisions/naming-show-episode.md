---
kind: decision
title: Parse show+episode from the first pipe-segment carrying an episode marker; nest under {deck_root}::{show}::{episode}
covers: autoanki/naming.py
---

## What was chosen

`parse_show_episode(video_title)` splits the title on `|` (Chinese
broadcaster uploads read `【去有风的地方】第1集 | 刘亦菲、李现主演 | Meet
Yourself EP1 | … | ENG SUB`) and takes the first segment containing an
episode marker: `SNNENN`, `EP\d+` / `Episode \d+`, bare `E\d+`, or `第\d+集`,
using whichever occurs earliest in that segment. The episode is normalised to
two-digit `EPNN` (or kept as `SNNENN`). The show is what comes before the
marker in that segment. If nothing does (`Show | Episode 100`), the first
marker-free segment is the show. `[Eng Sub]` and `(HD)` style tags are
stripped; `【…】` and `《…》` are unwrapped, because Chinese broadcasters put
the show name itself in them. The real Meet Yourself title yields
`AutoAnki::去有风的地方::EP01`.

`build_deck_name(deck_root, show, episode)` composes
`{deck_root}::{show}::{episode}` when the episode is known and
`{deck_root}::{show}` when it isn't. Any `::` inside the components is
replaced with `-` so a stray colon can't create an unintended nesting
level.

Both are wired into `cards.generate_deck` and `ankiconnect.push_to_anki`;
the CLI parses from `dl.title` and lets `--show` / `--episode` /
`--deck-root` override.

## What was rejected, and why

- **Try patterns in priority order across the whole title.** The first
  version did this; on the real title `EP1` (late, in the English segment)
  beat `第1集` (early), and the show became `【去有风的地方】第1集 | 刘亦菲、
  李现主演 | Meet Yourself`.
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
