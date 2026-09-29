"""CLI entry point: video URL in -> Anki deck out."""

import argparse
import shutil
import tempfile
from pathlib import Path

from autoanki.download import download
from autoanki.subtitles import parse_vtt
from autoanki.clip import extract_clips
from autoanki.translate import translate_segments
from autoanki.cards import generate_deck
from autoanki.morph import load_known_morphs, unknown_morphs


def _process_one(url: str, args, work_dir: Path) -> None:
    """Process a single video URL through the full pipeline."""
    # Stage 1: Download
    print("Downloading video and subtitles...")
    dl = download(url, work_dir / "download", cookies=args.cookies)
    print(f"  Video: {dl.video_path.name}")
    print(f"  Subs:  {dl.subtitle_path.name}")
    print(f"  Lang:  {dl.sub_lang}")
    print(f"  Title: {dl.title}")

    is_chinese_subs = dl.sub_lang.startswith("zh")

    # Stage 2: Parse subtitles
    print("Parsing subtitles...")
    segments = parse_vtt(dl.subtitle_path, require_chinese=is_chinese_subs, drop_noise=not args.keep_noise)
    print(f"  Found {len(segments)} segments")

    if not segments:
        print("No valid subtitle segments found. Skipping.")
        return

    # Stage 3: Extract clips
    print(f"Extracting {len(segments)} video clips (padding={args.clip_padding}s)...")
    clip_paths = extract_clips(
        dl.video_path, segments, work_dir / "clips", padding=args.clip_padding
    )
    print(f"  Extracted {len(clip_paths)} clips")

    # Stage 4: Get Chinese text + English translations
    if is_chinese_subs:
        if args.no_translate:
            translations = ["" for _ in segments]
            print("Skipping translation (--no-translate)")
        else:
            print(f"Translating {len(segments)} segments...")
            translations = translate_segments(segments)
            print(f"  Translated {len(translations)} segments")
    else:
        from autoanki.ocr_preprocessing import translate_en_to_zh

        translations = [seg.text for seg in segments]

        if args.no_ocr:
            print(f"Translating {len(segments)} English segments to Chinese...")
            chinese_texts = translate_en_to_zh(translations)
        else:
            from autoanki.ocr import ocr_segments  # lazy: PaddleOCR is heavy
            print(f"OCR-ing {len(segments)} frames for burned-in Chinese text...")
            chinese_texts = ocr_segments(dl.video_path, segments, work_dir)

            ocr_count = sum(1 for t in chinese_texts if t)
            empty_count = len(chinese_texts) - ocr_count
            print(f"  OCR: {ocr_count} segments with text, {empty_count} empty")

            if empty_count > len(segments) * 0.5:
                print("  >50% empty — using Claude to fill gaps...")
                empty_indices = [i for i, t in enumerate(chinese_texts) if not t]
                empty_english = [translations[i] for i in empty_indices]
                filled = translate_en_to_zh(empty_english)
                for idx, chinese in zip(empty_indices, filled):
                    chinese_texts[idx] = chinese
                print(f"  Claude filled {len(filled)} segments")

        # Claude post-correction
        if not args.no_ocr_correct and not args.no_ocr:
            from autoanki.ocr_correct import correct_ocr
            print(f"Correcting OCR with Claude ({len(chinese_texts)} segments)...")
            chinese_texts = correct_ocr(chinese_texts, translations)
            print(f"  Corrected {len(chinese_texts)} segments")

        for seg, chinese in zip(segments, chinese_texts):
            seg.text = chinese

        final_count = sum(1 for t in chinese_texts if t)
        print(f"  Final: {final_count}/{len(segments)} segments with Chinese text")

    # Stage 4a: CJK-side noise filter — watermarks, song/credit markers,
    # stage directions, cross-segment repeated static overlays.
    if not args.keep_noise:
        from autoanki.filters import is_noise_post_ocr, repeated_texts
        before = len(segments)
        repeated = repeated_texts((s.text for s in segments), threshold=3)
        noise_reasons: dict[str, int] = {}
        keep = []
        for s, t, c in zip(segments, translations, clip_paths):
            noise, reason = is_noise_post_ocr(s.text, repeated)
            if noise:
                noise_reasons[reason] = noise_reasons.get(reason, 0) + 1
                continue
            keep.append((s, t, c))
        segments = [s for s, _, _ in keep]
        translations = [t for _, t, _ in keep]
        clip_paths = [c for _, _, c in keep]
        dropped = before - len(segments)
        if dropped:
            breakdown = ", ".join(f"{k}={v}" for k, v in sorted(noise_reasons.items()))
            print(f"  noise filter: dropped {dropped}/{before} ({breakdown})")
        if not segments:
            print("Nothing survived the noise filter. Skipping.")
            return

    # Stage 4b: i+1 filter — drop segments where every morph is already known.
    if args.i_plus_one:
        known = load_known_morphs()
        before = len(segments)
        keep = [
            (s, t, c)
            for s, t, c in zip(segments, translations, clip_paths)
            if len(unknown_morphs(s.text, known)) == 1
        ]
        segments = [s for s, _, _ in keep]
        translations = [t for _, t, _ in keep]
        clip_paths = [c for _, _, c in keep]
        print(f"  i+1 filter: kept {len(segments)}/{before} segments with exactly 1 unknown morph")
        if not segments:
            print("Nothing survived the i+1 filter. Skipping.")
            return

    # Stage 5: Output cards
    if args.ankiconnect:
        from autoanki.ankiconnect import push_to_anki
        print("Pushing cards to Anki via AnkiConnect...")
        count = push_to_anki(dl.title, segments, translations, clip_paths)
        print(f"  Pushed {count} cards to deck AutoAnki::{dl.title}")
        print(f"\nDone! Cards are in Anki.")
    else:
        output_path = Path(args.output) if args.output else Path(f"{dl.title}.apkg")
        print("Generating Anki deck...")
        result = generate_deck(dl.title, segments, translations, clip_paths, output_path)
        print(f"  Deck saved to: {result}")
        print(f"\nDone! Import {result} into Anki.")


def main():
    # `autoanki setup` dispatches to the level-wizard subcommand; every other
    # invocation is the classic pipeline. Kept as a lightweight sniff at the
    # top of main() so `autoanki <url>` remains a single positional argparse.
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "setup":
        from autoanki.level.setup_cli import main as setup_main
        sys.exit(setup_main(sys.argv[2:]))

    parser = argparse.ArgumentParser(
        prog="autoanki",
        description="Generate Anki flashcards from Chinese video content.",
    )
    parser.add_argument("urls", nargs="+", help="YouTube or Bilibili video URL(s)")
    parser.add_argument(
        "-o", "--output",
        help="Output .apkg file path (default: <video-title>.apkg). Only for single URL.",
    )
    parser.add_argument(
        "--work-dir",
        help="Working directory for intermediate files (default: temp dir)",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Don't delete working directory after completion",
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Skip translation (English field will be empty)",
    )
    parser.add_argument(
        "--cookies",
        help="Path to cookies file (for login-required videos)",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip OCR, use Claude to translate English subs to Chinese instead",
    )
    parser.add_argument(
        "--no-ocr-correct",
        action="store_true",
        help="Skip Claude OCR post-correction step",
    )
    parser.add_argument(
        "--ankiconnect",
        action="store_true",
        help="Push cards to Anki via AnkiConnect (default http://localhost:8555, override with ANKICONNECT_URL) instead of .apkg",
    )
    parser.add_argument(
        "--clip-padding",
        type=float,
        default=0.4,
        help="Seconds of buffer before/after each subtitle when cutting clips (default: 0.4)",
    )
    parser.add_argument(
        "--i-plus-one",
        action="store_true",
        help="Only keep sentences with exactly one unknown morph (drops all-known and multi-unknown)",
    )
    parser.add_argument(
        "--keep-noise",
        action="store_true",
        help="Skip the song-lyric / credit / watermark / stage-direction / repeated-static filter",
    )

    args = parser.parse_args()

    if args.work_dir:
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        tmp = tempfile.mkdtemp(prefix="autoanki_")
        work_dir = Path(tmp)
        cleanup = not args.keep_work_dir

    try:
        for i, url in enumerate(args.urls):
            if len(args.urls) > 1:
                print(f"\n{'='*60}")
                print(f"  [{i + 1}/{len(args.urls)}] {url}")
                print(f"{'='*60}\n")

            video_work_dir = work_dir / f"video_{i}" if len(args.urls) > 1 else work_dir
            video_work_dir.mkdir(parents=True, exist_ok=True)

            try:
                _process_one(url, args, video_work_dir)
            except Exception as e:
                print(f"\nError processing {url}: {e}")
                if len(args.urls) > 1:
                    print("Continuing with next URL...")
                    continue
                raise
    finally:
        if cleanup:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
