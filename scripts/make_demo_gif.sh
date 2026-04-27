#!/usr/bin/env bash
# Build docs/demo.gif from the bundled .apkg as a 2x2 card grid.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APKG="$ROOT/Uj__X2BRhyo.apkg"
WORK="$ROOT/data/apkg_extract"
OUT="$ROOT/docs/demo.gif"
FONT_CJK="/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
FONT_LAT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

mkdir -p "$WORK" "$(dirname "$OUT")"
[[ -f "$WORK/0" ]] || unzip -oq "$APKG" -d "$WORK"

CW=380; CH=214; TH=88; FPS=10; DUR=4

draw_cell() {
  local idx=$1 zh=$2 en=$3 label=$4
  echo "[${idx}:v]scale=${CW}:${CH}:force_original_aspect_ratio=decrease,pad=${CW}:${CH}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,loop=loop=-1:size=999:start=0,trim=duration=${DUR},setpts=PTS-STARTPTS,pad=${CW}:$((CH+TH)):0:0:0x1f1f1f,drawtext=fontfile=${FONT_CJK}:text='${zh}':fontcolor=white:fontsize=28:x=(w-text_w)/2:y=${CH}+12,drawtext=fontfile=${FONT_LAT}:text='${en}':fontcolor=0xb0b0b0:fontsize=16:x=(w-text_w)/2:y=${CH}+52[${label}]"
}

C1=$(draw_cell 0 "这边请"        "This way, please"     a)
C2=$(draw_cell 1 "谢谢"          "Thank you"            b)
C3=$(draw_cell 2 "实在不好意思"  "Terribly sorry"       c)
C4=$(draw_cell 3 "您看要不然这样" "How about this"       d)

FILT="${C1};${C2};${C3};${C4};[a][b]hstack=inputs=2[t];[c][d]hstack=inputs=2[btm];[t][btm]vstack=inputs=2,fps=${FPS}[v]"

PAL="$WORK/_palette.png"
ffmpeg -y -i "$WORK/0" -i "$WORK/4" -i "$WORK/24" -i "$WORK/29" \
  -filter_complex "${FILT};[v]palettegen=max_colors=96[p]" -map "[p]" "$PAL" -loglevel error

ffmpeg -y -i "$WORK/0" -i "$WORK/4" -i "$WORK/24" -i "$WORK/29" -i "$PAL" \
  -filter_complex "${FILT};[v][4:v]paletteuse=dither=bayer:bayer_scale=5" \
  -loop 0 "$OUT" -loglevel error

rm -f "$PAL"
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
