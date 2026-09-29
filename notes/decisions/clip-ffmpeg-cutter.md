---
kind: decision
title: Cut one MP4 per segment with libx264/aac and a 0.4s pre/post padding default
covers: autoanki/clip.py
---

## What was chosen

`extract_clips()` runs one `ffmpeg` per segment with `-ss …` before `-i` for
fast seeking, `libx264 -preset fast -crf 23` video and `aac` mono 44.1kHz
audio, `+faststart` for progressive playback inside Anki, and
`avoid_negative_ts=make_zero` so seek offsets don't produce negative PTS.
Padding defaults to `0.4s` on both sides — bumped from the original 0.15s
because voice was hitting at t=0 with no lead-in, giving the learner no time
to orient before the line played.

## What was rejected, and why

- **Audio-only clips (mp3).** Video-plus-audio carries the situational
  context (who's speaking, tone, gesture) that a listening card needs; audio
  cards are a separate follow-up feature, not a replacement.
- **Batch encode via one long ffmpeg call.** Per-segment invocations are
  linear in count but trivially parallelizable later; the streaming print
  gives visible progress and each clip is independently cacheable/skippable.
- **Higher CRF for smaller files.** CRF 23 landed on ~350KB/clip in
  practice; going to 28 saves half but degrades text legibility on burned-in
  subs, which matters for the Reading card face.
