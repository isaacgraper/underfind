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


class ScanConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    every_minutes: int = Field(default=0, ge=0, description="Scheduled scan interval for the worker; 0 = manual scans only")
    max_age_days: int = Field(default=7, ge=1)
    max_duration_seconds: int = Field(default=180, ge=5)
    per_source_limit: int = Field(default=12, ge=1, le=50, description="Recent posts read per seed page / search")
    youtube_keyword_searches: int = Field(default=2, ge=0, description="search.list calls per scan (100 quota units each)")


class ScoringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weights: Dict[str, float] = Field(default_factory=lambda: {"velocity": 0.4, "ratio": 0.3, "engagement": 0.2, "relevance": 0.1})
    target_views_per_hour: float = Field(default=5000, gt=0, description="Views/hour that scores 100 on velocity")
    target_ratio: float = Field(default=10, gt=0, description="Views/followers that scores 100 on ratio")
    target_engagement: float = Field(default=0.08, gt=0, description="(likes+comments)/views that scores 100")
    min_score: float = Field(default=60, ge=0, le=100)


class AutoQueueConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    max_per_scan: int = Field(default=5, ge=0)
    mode: str = Field(default="subtitles", pattern="^(subtitles|dub)$")


class Niche(BaseModel):
    """A content niche: sourcing keywords and pages, scan/scoring settings, never-translate glossary, default hashtags."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    keywords: NicheKeywords = Field(default_factory=NicheKeywords)
    seed_pages: Dict[str, List[str]] = Field(default_factory=dict)
    regions: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    glossary: List[str] = Field(default_factory=list)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    auto_queue: AutoQueueConfig = Field(default_factory=AutoQueueConfig)


@lru_cache(maxsize=32)
def _load(path: Path, mtime: float) -> Niche:
    return Niche.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_niche(name: Optional[str], directory: Optional[Path] = None) -> Optional[Niche]:
    """config/niches/<name>.yaml, re-read when the file changes. None for no niche; KeyError for an unknown one."""
    if not name:
        return None

    path = (directory or NICHES_DIR) / f"{name}.yaml"

    if not path.exists():
        raise KeyError(f"Unknown niche '{name}': no {path}")

    return _load(path, path.stat().st_mtime)


def list_niches(directory: Optional[Path] = None) -> List[str]:
    return sorted(p.stem for p in (directory or NICHES_DIR).glob("*.yaml"))
