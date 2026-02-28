"""Translate English subtitles to Chinese using Claude CLI.

Fallback for when OCR can't extract burned-in Chinese subs.
"""

import json
import subprocess

CHUNK_SIZE = 150


def translate_en_to_zh(english_texts: list[str]) -> list[str]:
    """Translate English subtitle texts to Chinese using Claude CLI.

    Used as a fallback when OCR can't extract burned-in Chinese subs.
    Batches all texts into a single Claude call for efficiency.
    Chunks at 150 texts per call for very long videos.
    """
    if not english_texts:
        return []

    all_translations = []

    for chunk_start in range(0, len(english_texts), CHUNK_SIZE):
        chunk = english_texts[chunk_start : chunk_start + CHUNK_SIZE]

        numbered_lines = "\n".join(
            f"{i}: {text}" for i, text in enumerate(chunk)
        )

        prompt = (
            "Translate each numbered English line to natural spoken Chinese.\n"
            "Use everyday conversational Mandarin, not formal or literary style.\n"
            "Return ONLY a JSON array of strings, where index i is the "
            "translation of line i.\n"
            "Do not add explanations. Do not skip any lines.\n\n"
            f"{numbered_lines}"
        )

        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Claude CLI not found. Install it or use --no-translate."
            )

        response = json.loads(result.stdout)
        content = response.get("result", result.stdout)

        if isinstance(content, str):
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            translations = json.loads(content)
        else:
            translations = content

        if len(translations) != len(chunk):
            raise ValueError(
                f"Translation count mismatch: got {len(translations)}, "
                f"expected {len(chunk)}"
            )

        all_translations.extend(translations)

    return all_translations
