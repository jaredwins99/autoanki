"""Agent stage: decide which "unknown" tokens are really new vocabulary.

jieba + a known-word list flags tokens that aren't vocabulary a learner needs:
names (丽萨, 刘先生), compositional combinations of known words (生日快乐,
两万多, 喝点), and segmentation artifacts (人讨 from 讨不讨厌). Whether a token
is lexicalized vocabulary or a transparent combination is a judgment call,
so it goes to Claude with a fixed rubric rather than to a heuristic.

Every token that isn't judged `vocab` is added to the known set before the
i+1 filter and the highlight run.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

CATEGORIES = ("name", "transparent", "artifact", "vocab")
CHUNK_SIZE = 120
CACHE = Path(os.environ.get("AUTOANKI_CACHE", Path.home() / ".cache" / "autoanki")) / "vocab_judgments.json"

RUBRIC = """\
You are filtering flashcard targets for a Mandarin learner at about HSK 5.
Each numbered line is a token that a word segmenter (jieba) marked as not on
the learner's known-word list, with one sentence from a TV drama it appears
in, and a hint showing whether it splits into words the learner already knows.

Classify each token as exactly one of:
- "name": a person, place, brand or organisation name, nickname, or a
  surname + title/kinship term (刘先生, 许经理, 小李, 王姐).
- "transparent": a combination of words the learner already knows whose
  meaning is just their sum, so there is nothing new to learn
  (生日快乐, 过生日, 两万多, 喝点, 碎玻璃, 养狗).
- "artifact": not a real word; the segmenter cut in the wrong place, gluing
  parts of neighbouring words (人讨 in 讨不讨厌, 有妈 in 怎么有妈的声音).
- "vocab": a real word or fixed expression with meaning the learner would
  have to learn, even if its characters are familiar (警觉, 燕窝, 迷茫,
  乌龙, 逢年过节, 胰腺癌).

When unsure between "transparent" and "vocab", choose "vocab".

Return ONLY a JSON array with one object per line, in order:
[{"c": "<category>", "why": "<under 10 words>"}, ...]
No other text."""


def _known_split(token: str, known: set[str]) -> list[str] | None:
    """Split `token` into shorter known words if possible, preferring fewer pieces."""
    n = len(token)
    best: list[list[str] | None] = [[]] + [None] * n
    for end in range(1, n + 1):
        for start in range(end):
            piece = token[start:end]
            prev = best[start]
            if prev is not None and piece in known and len(piece) < n:
                cand = prev + [piece]
                if best[end] is None or len(cand) < len(best[end]):
                    best[end] = cand
    return best[n]


def _ask(lines: list[str]) -> list[dict]:
    prompt = RUBRIC + "\n\n" + "\n".join(f"{i}: {line}" for i, line in enumerate(lines))
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        capture_output=True, text=True, check=True,
    )
    content = json.loads(result.stdout).get("result", result.stdout)
    if isinstance(content, str):
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        content = json.loads(content)
    if len(content) != len(lines):
        raise ValueError(f"judge returned {len(content)} labels for {len(lines)} tokens")
    for item in content:
        if item.get("c") not in CATEGORIES:
            raise ValueError(f"judge returned unknown category: {item!r}")
    return content


def judge(examples: dict[str, str], known: set[str], profile_key: str) -> dict[str, dict]:
    """Classify each token in `examples` (token → example sentence).

    Results are cached in $AUTOANKI_CACHE/vocab_judgments.json. The cache is
    discarded when `profile_key` changes, since "transparent" depends on what
    the learner knows.
    """
    cache: dict = {}
    if CACHE.exists():
        cache = json.loads(CACHE.read_text())
    if cache.get("profile_key") != profile_key:
        cache = {"profile_key": profile_key, "tokens": {}}
    done = cache["tokens"]

    todo = [t for t in examples if t not in done]
    for start in range(0, len(todo), CHUNK_SIZE):
        chunk = todo[start : start + CHUNK_SIZE]
        lines = []
        for tok in chunk:
            split = _known_split(tok, known)
            hint = " + ".join(split) + " (all known)" if split else "does not split into known words"
            lines.append(f"{tok} | sentence: {examples[tok]} | split: {hint}")
        for tok, verdict in zip(chunk, _ask(lines)):
            done[tok] = {"c": verdict["c"], "why": verdict.get("why", ""), "example": examples[tok]}
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

    return {t: done[t] for t in examples}
