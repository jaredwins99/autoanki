"""Spoken-language check: which language is actually spoken in a clip."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np

_model = None


def _load():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    return _model


def _audio(clip: Path) -> np.ndarray:
    # ffmpeg rather than faster_whisper.decode_audio: PyAV 19 rejects the
    # metadata_errors argument that decode_audio passes.
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.float32)


def spoken_language(clip: Path, padding: float) -> tuple[str, float]:
    """Whisper's top language for the clip, ignoring the padding on each side."""
    audio = _audio(clip)
    pad = int(padding * 16000)
    core = audio[pad:len(audio) - pad] if len(audio) > 2 * pad + 8000 else audio
    lang, prob, _ = _load().detect_language(core)
    return lang, prob
