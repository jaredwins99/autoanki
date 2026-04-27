#!/usr/bin/env python3
"""Build docs/demo.gif: 2x2 grid of cards, one new word highlighted per card.

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
OUT = ROOT / "docs" / "demo.gif"

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
    pre: str
    target: str
    post: str
    en: str


CARDS = [
    Card("0",  "",     "这边",  "请",     "This way, please"),
    Card("19", "您没",  "受伤",  "吧",     "Are you hurt?"),
    Card("31", "我送您两张", "餐券", "",   "Two meal vouchers for you"),
    Card("26", "这周末行政", "套房", "订满了", "Suites are fully booked this weekend"),
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
        inputs += ["-i", str(WORK / c.file_id)]
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
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-i", str(palette),
         "-filter_complex",
         f"{full};[v][{len(inputs) // 2}:v]paletteuse=dither=bayer:bayer_scale=5",
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
