from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

from underfind.backend.core.constants import ROOT_DIR

NICHES_DIR = ROOT_DIR / "config" / "niches"


class NicheKeywords(BaseModel):
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)


class Niche(BaseModel):
    """A content niche: sourcing keywords and pages, never-translate glossary, default hashtags."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    keywords: NicheKeywords = Field(default_factory=NicheKeywords)
    seed_pages: Dict[str, List[str]] = Field(default_factory=dict)
    regions: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    glossary: List[str] = Field(default_factory=list)


@lru_cache(maxsize=32)
def _load(path: Path, mtime: float) -> Niche:
    return Niche.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_niche(name: Optional[str], directory: Path = NICHES_DIR) -> Optional[Niche]:
    """config/niches/<name>.yaml, re-read when the file changes. None for no niche; KeyError for an unknown one."""
    if not name:
        return None

    path = directory / f"{name}.yaml"

    if not path.exists():
        raise KeyError(f"Unknown niche '{name}': no {path}")

    return _load(path, path.stat().st_mtime)


def list_niches(directory: Path = NICHES_DIR) -> List[str]:
    return sorted(p.stem for p in directory.glob("*.yaml"))
