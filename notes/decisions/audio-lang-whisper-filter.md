---
kind: decision
title: Drop clips whose spoken language isn't Mandarin, using Whisper base language ID on the unpadded audio
covers: autoanki/audio_lang.py
---

## What was chosen

`spoken_language(clip, padding)` decodes the clip's audio with ffmpeg
(16 kHz mono), trims the padding from both ends so neighbouring lines don't
vote, and returns faster-whisper `base` (int8, all CPU threads)
`detect_language`'s top language. `cli.py` keeps a card only when that is
`zh`, and runs this after the i+1 filter so only surviving cards pay the
~1.5 s/clip cost. `--keep-non-mandarin` skips it.

Motivating case: in Meet Yourself EP1 the lead speaks English to foreign
hotel guests while the burned-in subtitle shows the Chinese translation
(退房吗 over spoken "Check out?"). Such cards pass every text filter but
teach nothing by ear.

## What was rejected, and why

- **Drop only when English outranks Chinese.** Clip #2 (spoken "Good
  morning") came back `th` 0.95, `zh` 0.04, `en` 0.00. Requiring `zh` as the
  top language dropped all five English-audio clips tested and kept all nine
  Chinese ones, including a low-confidence `zh` 0.25.
- **`faster_whisper.decode_audio`.** PyAV 19 rejects its `metadata_errors`
  argument; ffmpeg is already a hard dependency.
- **Language ID on the full padded clip.** With 0.5 s of neighbouring
  dialogue on each side, a short line can be outvoted by its neighbours.
- **Text heuristics (English cue looks like greeting, etc.).** Whether the
  audio is Mandarin is a property of the audio; only listening to it answers.
