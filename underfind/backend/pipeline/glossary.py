from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List, Optional

from underfind.backend.core.niches import load_niche


def load_glossary(
    niche: Optional[str] = None,
    extra: Optional[Iterable[str]] = None,
) -> List[str]:
    """Terms kept verbatim: the page's niche preset + the page's own list + GLOSSARY_FILE (a JSON list of strings)."""
    terms: List[str] = []
    preset = load_niche(niche)

    if preset:
        terms.extend(preset.glossary)

    terms.extend(extra or [])
    extra_path = os.environ.get("GLOSSARY_FILE")

    if extra_path and Path(extra_path).exists():
        terms.extend(t for t in json.loads(Path(extra_path).read_text(encoding="utf-8")) if isinstance(t, str))

    return list(dict.fromkeys(t.strip() for t in terms if t and t.strip()))
