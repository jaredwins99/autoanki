"""Post-correct OCR results using Claude with English subtitle context."""

import hashlib
import json
import subprocess
from pathlib import Path

CHUNK_SIZE = 150

RULES = (
    "Rules:\n"
    "- The OCR is usually exactly what is on screen. Keep it verbatim unless one of these applies:\n"
    "  (a) a character is misread: a traditional form (沒→没), a look-alike character, or a "
    "character dropped at the start or end of the line;\n"
    "  (b) the OCR includes text that is not the subtitle (watermarks like 'WX', channel logos, "
    "character name labels): remove it;\n"
    "  (c) two subtitle lines were read in the wrong order: restore the order.\n"
    "- Never add, remove, or swap words to match the English more closely. The English "
    "subtitle is a loose translation of the Chinese, not a word-for-word one.\n"
    "- If the OCR Chinese is empty or garbage (random characters, partial words), translate the "
    "English to natural spoken Chinese instead.\n"
    "- Return ONLY a JSON array of strings, index i = corrected Chinese for line i.\n"
    "- Do not add explanations. Do not skip any lines.\n"
)
_RULES_KEY = hashlib.sha1(RULES.encode()).hexdigest()[:12]


def correct_ocr(
    ocr_texts: list[str], english_texts: list[str], cache_path: Path | None = None
) -> list[str]:
    """Fix OCR errors using English subtitles as context.

    For garbage/empty OCR, translates English to Chinese instead. With
    `cache_path`, lines already corrected under the same rules are reused, so
    re-running an episode doesn't re-roll text that was already checked.
    """
    assert len(ocr_texts) == len(english_texts)
    if not ocr_texts:
        return []

    cache: dict = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())
    if cache.get("rules") != _RULES_KEY:
        cache = {"rules": _RULES_KEY, "lines": {}}
    lines = cache["lines"]
    key = lambda ocr, eng: f"{ocr}\x1f{eng}"
    todo = [(o, e) for o, e in dict.fromkeys(zip(ocr_texts, english_texts)) if key(o, e) not in lines]

    for chunk_start in range(0, len(todo), CHUNK_SIZE):
        ocr_chunk = [o for o, _ in todo[chunk_start : chunk_start + CHUNK_SIZE]]
        eng_chunk = [e for _, e in todo[chunk_start : chunk_start + CHUNK_SIZE]]

        numbered_lines = "\n".join(
            f"{i}: OCR={ocr} | EN={eng}"
            for i, (ocr, eng) in enumerate(zip(ocr_chunk, eng_chunk))
        )

        prompt = (
            "You are correcting Chinese OCR output from a TV drama.\n"
            "Each line has: the raw OCR Chinese text and the English subtitle.\n\n"
            f"{RULES}\n"
            f"{numbered_lines}"
        )

        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            capture_output=True, text=True, check=True,
        )

        response = json.loads(result.stdout)
        content = response.get("result", result.stdout)

        if isinstance(content, str):
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            corrected = json.loads(content)
        else:
            corrected = content

        if len(corrected) != len(ocr_chunk):
            raise ValueError(
                f"Correction count mismatch: got {len(corrected)}, expected {len(ocr_chunk)}"
            )

        for o, e, c in zip(ocr_chunk, eng_chunk, corrected):
            lines[key(o, e)] = c
        if cache_path:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

    return [lines[key(o, e)] for o, e in zip(ocr_texts, english_texts)]
