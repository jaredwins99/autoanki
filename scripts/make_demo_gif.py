#!/usr/bin/env python3
"""Build legibility/docs/demo.gif: 2x2 grid of cards, one new word highlighted per card.

Renders text panels with PIL (so a single word can be colored), then composes
four extracted .apkg clips into a grid via ffmpeg.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
APKG = ROOT / "Uj__X2BRhyo.apkg"
WORK = ROOT / "data" / "apkg_extract"
OUT = ROOT / "legibility" / "docs" / "demo.gif"

FONT_CJK = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
FONT_LAT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

CW, CH, TH = 380, 214, 100
FPS, DUR = 10, 4
ZH_SIZE, EN_SIZE = 28, 16
PANEL_BG = (31, 31, 31, 255)
ZH_COLOR = (255, 255, 255, 255)
HL_COLOR = (251, 192, 45, 255)  # AnkiMorphs-style focus-morph yellow
EN_COLOR = (176, 176, 176, 255)


@dataclass
class Card:
    file_id: str
    start: float  # seconds into clip where subtitle appears
    dur: float    # seconds the subtitle stays on screen
    pre: str
    target: str
    post: str
    en: str


CARDS = [
    Card("4",   0.30, 1.70, "你能告诉我您的", "房号", "吗", "Can you tell me your room number?"),
    Card("120", 0.50, 1.00, "",             "考察", "了两家酒店", "Inspected two hotels"),
    Card("130", 0.55, 1.50, "给你又寄了不少", "燕窝", "呀", "Sent you more bird's nest"),
    Card("150", 0.50, 1.30, "你说咱那么努力", "赚钱", "",   "We work so hard to earn money"),
]


def render_panel(card: Card, path: Path) -> None:
    img = Image.new("RGBA", (CW, TH), PANEL_BG)
    draw = ImageDraw.Draw(img)
    zh_font = ImageFont.truetype(FONT_CJK, ZH_SIZE)
    en_font = ImageFont.truetype(FONT_LAT, EN_SIZE)

    def w(text: str, font) -> int:
        return draw.textbbox((0, 0), text, font=font)[2]

    pre_w, tgt_w, post_w = w(card.pre, zh_font), w(card.target, zh_font), w(card.post, zh_font)
    total = pre_w + tgt_w + post_w
    x = (CW - total) // 2
    y_zh = 14

    if card.pre:
        draw.text((x, y_zh), card.pre, font=zh_font, fill=ZH_COLOR)
    draw.text((x + pre_w, y_zh), card.target, font=zh_font, fill=HL_COLOR)
    if card.post:
        draw.text((x + pre_w + tgt_w, y_zh), card.post, font=zh_font, fill=ZH_COLOR)

    en_w = w(card.en, en_font)
    draw.text(((CW - en_w) // 2, 56), card.en, font=en_font, fill=EN_COLOR)
    img.save(path)


def build() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not (WORK / "0").exists():
        subprocess.run(["unzip", "-oq", str(APKG), "-d", str(WORK)], check=True)

    panels = []
    for i, c in enumerate(CARDS):
        p = WORK / f"_panel_{i}.png"
        render_panel(c, p)
        panels.append(p)

    inputs: list[str] = []
    for c in CARDS:
        inputs += ["-ss", str(c.start), "-t", str(c.dur), "-i", str(WORK / c.file_id)]
    for p in panels:
        inputs += ["-i", str(p)]

    chains = []
    for i in range(4):
        chains.append(
            f"[{i}:v]scale={CW}:{CH}:force_original_aspect_ratio=decrease,"
            f"pad={CW}:{CH}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,"
            f"loop=loop=-1:size=999:start=0,trim=duration={DUR},setpts=PTS-STARTPTS,"
            f"pad={CW}:{CH + TH}:0:0:0x1f1f1f[v{i}];"
            f"[v{i}][{i + 4}:v]overlay=0:{CH}[c{i}]"
        )
    layout = (
        "[c0][c1]hstack=inputs=2[top];"
        "[c2][c3]hstack=inputs=2[bot];"
        f"[top][bot]vstack=inputs=2,fps={FPS}[v]"
    )
    full = ";".join(chains) + ";" + layout

    palette = WORK / "_palette.png"
    subprocess.run(
        ["ffmpeg", "-y", *inputs,
         "-filter_complex", f"{full};[v]palettegen=max_colors=96[p]",
         "-map", "[p]", str(palette), "-loglevel", "error"],
        check=True,
    )
    palette_idx = len(CARDS) * 2  # 4 video inputs + 4 panel inputs => palette is index 8
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-i", str(palette),
         "-filter_complex",
         f"{full};[v][{palette_idx}:v]paletteuse=dither=bayer:bayer_scale=5",
         "-loop", "0", str(OUT), "-loglevel", "error"],
        check=True,
    )

    palette.unlink()
    for p in panels:
        p.unlink()
    size = OUT.stat().st_size / 1024 / 1024
    print(f"wrote {OUT} ({size:.1f}M)")


if __name__ == "__main__":
    build()
