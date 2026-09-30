"""CLI entry point: video URL in -> Anki deck out."""

import argparse
import os
import shutil
import tempfile
from pathlib import Path

from autoanki.download import _extract_video_id, download
from autoanki.subtitles import parse_vtt
from autoanki.clip import extract_clips
from autoanki.translate import translate_segments
from autoanki.cards import generate_deck
from autoanki.morph import load_known_morphs, unknown_morphs

# Downloads live outside the (possibly temporary) work dir so a run's cleanup
# never deletes a source video; re-downloading can be blocked by YouTube.
DOWNLOAD_CACHE = Path(os.environ.get("AUTOANKI_CACHE", Path.home() / ".cache" / "autoanki"))


def _process_one(url: str, args, work_dir: Path) -> None:
    """Process a single video URL through the full pipeline."""
    # Stage 1: Download
    print("Downloading video and subtitles...")
    video_id = _extract_video_id(url) or "unknown"
    dl = download(url, DOWNLOAD_CACHE / video_id / "download", cookies=args.cookies)
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
            chinese_texts = correct_ocr(chinese_texts, translations, cache_path=work_dir / "correct_cache.json")
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

    known = load_known_morphs()

    # Stage 4a2: vocab judge — an agent classifies every unknown token as
    # name / transparent combination / segmentation artifact / real vocab.
    # Everything but real vocab counts as known from here on.
    if not args.no_vocab_judge:
        from autoanki.level.profile import Profile
        from autoanki.vocab_judge import judge
        examples: dict[str, str] = {}
        for s in segments:
            for tok in unknown_morphs(s.text, known):
                examples.setdefault(tok, s.text)
        profile = Profile.load()
        profile_key = profile.updated_at.isoformat() if profile else "baseline-csv"
        print(f"Judging {len(examples)} unknown tokens (names / combinations / artifacts / vocab)...")
        verdicts = judge(examples, known, profile_key)
        counts: dict[str, int] = {}
        for tok, v in verdicts.items():
            counts[v["c"]] = counts.get(v["c"], 0) + 1
            if v["c"] != "vocab":
                known.add(tok)
        print("  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    # Stage 4b: i+1 filter — drop segments where every morph is already known.
    if args.i_plus_one:
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

    # Stage 4c: spoken-language filter — drop clips where the speech isn't
    # Mandarin (e.g. a character speaking English to a foreign guest while the
    # burned-in subtitle shows the Chinese translation).
    if not args.keep_non_mandarin:
        from autoanki.audio_lang import spoken_language
        before = len(segments)
        keep, other = [], {}
        for s, t, c in zip(segments, translations, clip_paths):
            lang, _ = spoken_language(c, args.clip_padding)
            if lang == "zh":
                keep.append((s, t, c))
            else:
                other[lang] = other.get(lang, 0) + 1
        segments = [s for s, _, _ in keep]
        translations = [t for _, t, _ in keep]
        clip_paths = [c for _, _, c in keep]
        if other:
            breakdown = ", ".join(f"{k}={v}" for k, v in sorted(other.items()))
            print(f"  language filter: dropped {before - len(segments)}/{before} non-Mandarin clips ({breakdown})")
        if not segments:
            print("Nothing survived the language filter. Skipping.")
            return

    # Stage 4d: English from the card's own Chinese. English subtitle lines
    # split and reorder clauses differently from the burned-in Chinese, so the
    # cue's English often translates a neighbouring Chinese line.
    if not is_chinese_subs and not args.no_translate:
        print(f"Translating {len(segments)} Chinese lines to English...")
        translations = translate_segments(segments)

    # Stage 5: Output cards — resolve deck naming
    from autoanki.naming import parse_show_episode, build_deck_name

    parsed_show, parsed_episode = parse_show_episode(dl.title)
    show = args.show or parsed_show
    episode = args.episode or parsed_episode
    deck_name = build_deck_name(args.deck_root, show, episode)

    if args.ankiconnect:
        from autoanki.ankiconnect import push_to_anki
        print(f"Pushing cards to Anki via AnkiConnect (deck: {deck_name})...")
        count = push_to_anki(
            dl.title, segments, translations, clip_paths,
            deck_root=args.deck_root, show=show, episode=episode, known=known,
        )
        print(f"  Pushed {count} cards to {deck_name}")
        print(f"\nDone! Cards are in Anki.")
    else:
        output_path = Path(args.output) if args.output else Path(f"{dl.title}.apkg")
        print(f"Generating Anki deck (deck: {deck_name})...")
        result = generate_deck(
            dl.title, segments, translations, clip_paths, output_path,
            deck_root=args.deck_root, show=show, episode=episode, known=known,
        )
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
        "--no-vocab-judge",
        action="store_true",
        help="Skip the agent pass that stops names, transparent combinations and segmentation artifacts from counting as new words",
    )
    parser.add_argument(
        "--keep-non-mandarin",
        action="store_true",
        help="Skip the spoken-language check that drops clips whose audio isn't Mandarin",
    )
    parser.add_argument(
        "--keep-noise",
        action="store_true",
        help="Skip the song-lyric / credit / watermark / stage-direction / repeated-static filter",
    )
    parser.add_argument(
        "--deck-root",
        default="AutoAnki",
        help="Top-level Anki deck name (default: AutoAnki). Full deck becomes <root>::<show>::<episode>",
    )
    parser.add_argument(
        "--show",
        help="Show name override; if omitted, autoanki parses it from the video title.",
    )
    parser.add_argument(
        "--episode",
        help="Episode label override (e.g. EP01, S01E03); if omitted, autoanki parses it from the video title.",
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
