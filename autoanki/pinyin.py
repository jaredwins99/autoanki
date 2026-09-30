"""Tone-marked pinyin per jieba word, as HTML ruby for the card back."""

from __future__ import annotations

import html
import re

import jieba
from pypinyin import Style, pinyin

_HAN_RE = re.compile(r"[一-鿿]")


def pinyin_ruby(text: str) -> str:
    """`<ruby>退房<rt>tuìfáng</rt></ruby> <ruby>吗<rt>ma</rt></ruby>`.

    Pinyin is computed per word so pypinyin's phrase dictionary resolves
    characters with several readings (行 in 行李 vs 银行).
    """
    parts = []
    for word in jieba.cut(text):
        if not word.strip():
            continue
        if _HAN_RE.search(word):
            reading = "".join(syllable[0] for syllable in pinyin(word, style=Style.TONE))
            parts.append(f"<ruby>{html.escape(word)}<rt>{html.escape(reading)}</rt></ruby>")
        else:
            parts.append(html.escape(word))
    return " ".join(parts)
