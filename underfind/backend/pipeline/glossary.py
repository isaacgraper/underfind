from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

# Names and titles that stay exactly as written in every language.
GTA6_GLOSSARY: List[str] = [
    "GTA VI",
    "GTA 6",
    "Grand Theft Auto VI",
    "Rockstar Games",
    "Rockstar",
    "Take-Two",
    "Vice City",
    "Leonida",
    "Leonida Keys",
    "Port Gellhorn",
    "Ambrosia",
    "Grassrivers",
    "Mount Kalaga",
    "Lucia",
    "Jason",
    "GTA Online",
    "PS5",
    "Xbox Series X|S",
]


def load_glossary() -> List[str]:
    """Built-in GTA VI terms plus any extra terms from GLOSSARY_FILE (a JSON list of strings)."""
    terms = list(GTA6_GLOSSARY)
    extra_path = os.environ.get("GLOSSARY_FILE")

    if extra_path and Path(extra_path).exists():
        extra = json.loads(Path(extra_path).read_text(encoding="utf-8"))
        terms.extend(t for t in extra if isinstance(t, str) and t not in terms)

    return terms
