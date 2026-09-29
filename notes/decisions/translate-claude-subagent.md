---
kind: decision
title: Chinese → English translation runs through the Claude CLI as a batched subprocess, not an API SDK
covers: autoanki/translate.py
---

## What was chosen

`translate_segments()` groups segments into 150-line chunks, formats each
chunk as `i: <text>` lines, sends the prompt to `claude -p …
--output-format json` as a subprocess, unwraps `{"result": "..."}` (which
may itself be a JSON string with fenced code), and expects an array whose
length matches the chunk. A `FileNotFoundError` for the `claude` binary
raises a clear error pointing at `--no-translate` as the escape hatch.

## What was rejected, and why

- **Anthropic API SDK.** Would require a managed API key, billing setup,
  and rate-limit handling. The Claude CLI is already installed on the
  developer's box for other work and inherits its auth from that install.
- **Google Translate / DeepL.** Extra credentials, worse for TV dialogue
  colloquialism, and adds a second external dependency to a pipeline that
  otherwise runs Claude for every LLM step.
- **Unbounded batch size.** Long contexts degrade instruction adherence and
  fail non-atomically; 150 lines is empirically small enough that Claude
  returns a well-formed array in one shot and large enough that per-call
  overhead stays low.
