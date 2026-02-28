"""Translate Chinese segments to English using Claude CLI."""

import json
import subprocess

from autoanki.subtitles import Segment

CHUNK_SIZE = 150


def translate_segments(segments: list[Segment]) -> list[str]:
    """Translate Chinese segments to English using Claude CLI in batches."""
    if not segments:
        return []

    all_translations = []

    for chunk_start in range(0, len(segments), CHUNK_SIZE):
        chunk = segments[chunk_start : chunk_start + CHUNK_SIZE]

        numbered_lines = "\n".join(
            f"{i}: {seg.text}" for i, seg in enumerate(chunk)
        )

        prompt = (
            "Translate each numbered Chinese line to natural English.\n"
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
