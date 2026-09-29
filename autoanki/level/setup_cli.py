"""TUI wizard for creating a Profile.

Invoked as `python -m autoanki.level.setup_cli` or via `autoanki setup`.
Interactive prompts guide the user through picking a source mode and
producing a persisted `profile.yaml`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from autoanki.level.profile import DEFAULT_PATH, Profile


def _read(question: str) -> str:
    """input() but hitting EOF (piped from /dev/null etc.) returns ''."""
    try:
        return input(question).strip()
    except EOFError:
        return ""


def _prompt(question: str, choices: list[str], default: str | None = None) -> str:
    tail = f" [{'/'.join(choices)}]"
    if default:
        tail += f" (default: {default})"
    while True:
        raw = _read(f"{question}{tail}: ").lower()
        if not raw and default:
            return default
        if raw in choices:
            return raw
        print(f"  answer must be one of {', '.join(choices)}")


def _prompt_int(question: str, lo: int, hi: int, default: int | None = None) -> int:
    tail = f" [{lo}-{hi}]"
    if default is not None:
        tail += f" (default: {default})"
    while True:
        raw = _read(f"{question}{tail}: ")
        if not raw and default is not None:
            return default
        try:
            n = int(raw)
        except ValueError:
            print("  needs an integer")
            continue
        if lo <= n <= hi:
            return n
        print(f"  needs to be between {lo} and {hi}")


def build_hsk_profile(band: int) -> Profile:
    """HSK baseline as the known set, jieba-compound-expanded.

    Uses the shipped CSV (HSK words + compounds built from known characters),
    not the raw HSK word list: jieba segments sentences into compounds like
    房号, and a raw-word known set marks those unknown even when every
    character is known, which makes i+1 drop nearly every sentence.
    Per-band separation isn't shipped yet, so `band` is recorded only.
    """
    from autoanki.morph import load_baseline_csv

    return Profile(source="hsk", hsk_baseline=band, known_morphs=load_baseline_csv())


def build_anki_profile(deck_filter: str | None) -> Profile:
    from autoanki.level.anki_import import scan_mature_morphs

    print(f"  Querying Anki for mature cards (ivl >= 21{' in deck ' + deck_filter if deck_filter else ''})...")
    morphs = scan_mature_morphs(deck_filter=deck_filter)
    print(f"  Found {len(morphs)} distinct known morphs across mature cards.")
    return Profile(source="anki", known_morphs=morphs, anki_deck_filter=deck_filter)


def build_hybrid_profile(band: int, deck_filter: str | None) -> Profile:
    from autoanki.level.anki_import import scan_mature_morphs

    from autoanki.morph import load_baseline_csv

    base = load_baseline_csv()
    print(f"  Querying Anki for mature cards...")
    anki = scan_mature_morphs(deck_filter=deck_filter)
    print(f"  Anki mature morphs: {len(anki)}")
    combined = base | anki
    print(f"  Hybrid total (HSK baseline union Anki mature): {len(combined)}")
    return Profile(
        source="hybrid",
        hsk_baseline=band,
        known_morphs=combined,
        anki_deck_filter=deck_filter,
    )


def run(mode: str | None = None, path: Path = DEFAULT_PATH) -> Profile:
    print(f"autoanki setup — will write to {path}")
    if not mode:
        mode = _prompt(
            "How should we bootstrap your known-morph set?",
            choices=["hsk", "anki", "hybrid", "quiz"],
            default="hsk",
        )

    if mode == "hsk":
        band = _prompt_int("HSK band you're comfortable with", lo=1, hi=6, default=5)
        profile = build_hsk_profile(band)
    elif mode == "anki":
        raw = input("Deck filter (blank = all decks): ").strip() or None
        profile = build_anki_profile(raw)
    elif mode == "hybrid":
        band = _prompt_int("HSK baseline band", lo=1, hi=6, default=5)
        raw = input("Anki deck filter (blank = all decks): ").strip() or None
        profile = build_hybrid_profile(band, raw)
    elif mode == "quiz":
        print("  quiz mode is not yet implemented — see notes/open/quiz-corpus.md.")
        sys.exit(2)
    else:
        raise ValueError(f"unknown mode: {mode}")

    profile.updated_at = datetime.now(timezone.utc)
    written = profile.save(path)
    print(f"  Profile written: {written}  ({len(profile.known_morphs)} morphs)")
    return profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autoanki setup", description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["hsk", "anki", "hybrid", "quiz"], default=None)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)
    run(mode=args.mode, path=args.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
