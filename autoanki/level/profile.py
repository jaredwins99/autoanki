"""Per-user vocabulary profile: which morphs the learner already knows.

A `Profile` is the single source of truth for the i+1 filter and the
highlight. It is persisted to `~/.config/autoanki/profile.yaml` (XDG
default; override with `AUTOANKI_PROFILE` env var) and loaded once at the
top of every autoanki run.

Four `source` modes populate a profile — all end up with the same
`known_morphs: set[str]`:

- **hsk**: user picks HSK band N; known = union of HSK 1..N from the
  shipped `data/hsk1-5_known_morphs.csv`. Coarsest, fastest to set up.
- **anki**: query the running AnkiConnect instance for mature cards
  (`prop:ivl>=21`), extract Chinese fields, tokenise with jieba, union.
- **quiz**: adaptive quiz over sample sentences; user marks known /
  one-new-word / too-hard; Bayesian narrowing over morph frequency.
- **hybrid**: HSK baseline, plus quiz corrections, plus Anki additions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

try:
    import yaml
except ImportError:  # pragma: no cover — yaml is a light dep
    yaml = None  # type: ignore[assignment]


Source = Literal["hsk", "anki", "quiz", "hybrid"]

DEFAULT_PATH = Path(
    os.environ.get(
        "AUTOANKI_PROFILE",
        Path.home() / ".config" / "autoanki" / "profile.yaml",
    )
)


@dataclass
class Profile:
    """The user's known-morph state and how it was derived."""

    source: Source
    known_morphs: set[str] = field(default_factory=set)
    hsk_baseline: int | None = None
    anki_deck_filter: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def save(self, path: Path = DEFAULT_PATH) -> Path:
        if yaml is None:
            raise RuntimeError("PyYAML is required to persist profiles. `pip install pyyaml`.")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "source": self.source,
            "hsk_baseline": self.hsk_baseline,
            "anki_deck_filter": self.anki_deck_filter,
            "updated_at": self.updated_at.isoformat(),
            "known_morphs": sorted(self.known_morphs),
        }
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        return path

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "Profile | None":
        """Return the persisted profile, or None if no profile exists."""
        if yaml is None or not path.exists():
            return None
        data = yaml.safe_load(path.read_text()) or {}
        return cls(
            source=data.get("source", "hsk"),
            known_morphs=set(data.get("known_morphs", [])),
            hsk_baseline=data.get("hsk_baseline"),
            anki_deck_filter=data.get("anki_deck_filter"),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
        )
