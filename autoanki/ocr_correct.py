"""Post-correct OCR results using Claude with English subtitle context."""

import json
import subprocess

CHUNK_SIZE = 150


def correct_ocr(ocr_texts: list[str], english_texts: list[str]) -> list[str]:
    """Fix OCR errors using English subtitles as context.

    For garbage/empty OCR, translates English to Chinese instead.
    """
    assert len(ocr_texts) == len(english_texts)
    if not ocr_texts:
        return []

    all_corrected = []

    for chunk_start in range(0, len(ocr_texts), CHUNK_SIZE):
        ocr_chunk = ocr_texts[chunk_start : chunk_start + CHUNK_SIZE]
        eng_chunk = english_texts[chunk_start : chunk_start + CHUNK_SIZE]

        numbered_lines = "\n".join(
            f"{i}: OCR={ocr} | EN={eng}"
            for i, (ocr, eng) in enumerate(zip(ocr_chunk, eng_chunk))
        )

        prompt = (
            "You are correcting Chinese OCR output from a TV drama.\n"
            "Each line has: the raw OCR Chinese text and the correct English subtitle.\n\n"
            "Rules:\n"
            "- If the OCR Chinese is mostly correct, fix minor character errors using English as context.\n"
            "- If the OCR Chinese is empty or garbage (random characters, partial words, "
            "watermarks like 'WX', character name labels), translate the English to natural "
            "spoken Chinese instead.\n"
            "- Keep the Chinese natural and colloquial — this is TV dialogue, not formal writing.\n"
            "- Return ONLY a JSON array of strings, index i = corrected Chinese for line i.\n"
            "- Do not add explanations. Do not skip any lines.\n\n"
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

        all_corrected.extend(corrected)

    return all_corrected
