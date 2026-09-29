---
kind: decision
title: One yt-dlp call downloads video + every candidate Chinese sub track, with cache-by-video-id reuse
covers: autoanki/download.py
---

## What was chosen

`download()` extracts the video id from the URL (YouTube 11-char or Bilibili
BV/av) and returns an earlier download if `<id>.mp4` + a preferred `.vtt`
already sit in the output dir. Otherwise it makes a single `yt-dlp`
invocation that asks for the best MP4+M4A, writes both manual and
auto-generated subs across the full `PREFERRED_SUB_LANGS` list
(`zh-Hans, zh, zh-CN, zh-Hant, zh-TW, zh-Hans-en, zh-Hant-en, en`), converts
to VTT, prints info-JSON to stdout, and paces with `--sleep-requests 1`.
`_find_subtitle` walks the preferred list in order and returns the first
match.

## What was rejected, and why

- **Multiple yt-dlp calls (probe metadata, then download).** Two-plus calls
  per video reliably tripped YouTube's rate limiter in early runs
  (`legibility/docs/process.md` §2 Problem 2); merging into one call is the
  fix.
- **Chinese-only sub download.** Some Chinese dramas ship only English
  subtitles because YouTube classifies them as English-audio content; the
  fallback lets the OCR path recover the Chinese later.
- **Delete on failure.** Partial downloads are left in place because the
  video-id cache reuses them on retry; a truly broken file is caught by the
  `FileNotFoundError` at the end.
