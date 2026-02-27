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
from autoanki.ocr import ocr_segments


def main():
    parser = argparse.ArgumentParser(
        prog="autoanki",
        description="Generate Anki flashcards from Chinese video content.",
    )
    parser.add_argument("url", help="YouTube or Bilibili video URL")
    parser.add_argument(
        "-o", "--output",
        help="Output .apkg file path (default: <video-title>.apkg)",
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

    args = parser.parse_args()

    # Set up working directory
    if args.work_dir:
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        tmp = tempfile.mkdtemp(prefix="autoanki_")
        work_dir = Path(tmp)
        cleanup = not args.keep_work_dir

    try:
        # Stage 1: Download
        print("Downloading video and subtitles...")
        dl = download(args.url, work_dir / "download")
        print(f"  Video: {dl.video_path.name}")
        print(f"  Subs:  {dl.subtitle_path.name}")
        print(f"  Lang:  {dl.sub_lang}")
        print(f"  Title: {dl.title}")

        is_chinese_subs = dl.sub_lang.startswith("zh")

        # Stage 2: Parse subtitles
        print("Parsing subtitles...")
        segments = parse_vtt(dl.subtitle_path, require_chinese=is_chinese_subs)
        print(f"  Found {len(segments)} segments")

        if not segments:
            print("No valid subtitle segments found. Exiting.")
            return

        # Stage 3: Extract clips
        print(f"Extracting {len(segments)} video clips...")
        clip_paths = extract_clips(dl.video_path, segments, work_dir / "clips")
        print(f"  Extracted {len(clip_paths)} clips")

        # Stage 4: Get Chinese text + English translations
        if is_chinese_subs:
            # Chinese subs available: translate to English
            if args.no_translate:
                translations = ["" for _ in segments]
                print("Skipping translation (--no-translate)")
            else:
                print(f"Translating {len(segments)} segments...")
                translations = translate_segments(segments)
                print(f"  Translated {len(translations)} segments")
        else:
            # English subs only: OCR video for Chinese, use English text as translations
            print(f"OCR-ing {len(segments)} frames for burned-in Chinese text...")
            translations = [seg.text for seg in segments]  # English text becomes translations
            chinese_texts = ocr_segments(dl.video_path, segments, work_dir)
            # Replace segment text with OCR'd Chinese
            for seg, chinese in zip(segments, chinese_texts):
                seg.text = chinese
            print(f"  OCR complete, {sum(1 for t in chinese_texts if t)} segments with text")

        # Stage 5: Generate deck
        output_path = Path(args.output) if args.output else Path(f"{dl.title}.apkg")
        print("Generating Anki deck...")
        result = generate_deck(dl.title, segments, translations, clip_paths, output_path)
        print(f"  Deck saved to: {result}")

        print(f"\nDone! Import {result} into Anki.")

    finally:
        if cleanup:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
