from __future__ import annotations

import re
from typing import Optional

from underfind.backend.core.constants import (
    MIN_SUBSCRIBER_BASE,
    VIRAL_THRESHOLD_EXTREME,
    VIRAL_THRESHOLD_OUTLIER,
    VIRAL_THRESHOLD_NEUTRAL,
)


def parse_iso8601_duration(duration_str: Optional[str]) -> int:
    """Converts ISO 8601 duration format (e.g., PT1M30S or PT45S) to total seconds."""
    if not duration_str or not isinstance(duration_str, str):
        return 0

    pattern = re.compile(r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?")
    match = pattern.match(duration_str.upper())

    if not match:
        return 0

    parts = match.groupdict()
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)

    return hours * 3600 + minutes * 60 + seconds


def calculate_viral_ratio(
    views: Optional[int],
    subscribers: Optional[int],
    min_base: int = MIN_SUBSCRIBER_BASE,
) -> float:
    """Calculates viral breakout ratio: views / max(subscribers, min_base)."""
    if not views:
        return 0.0

    subs_base = max(subscribers or 0, min_base)
    return round(float(views) / float(subs_base), 2)


def classify_viral_tier(viral_ratio: float) -> str:
    """Classifies a viral ratio into a standardized descriptive tier."""
    if viral_ratio >= VIRAL_THRESHOLD_EXTREME:
        return "viral"

    if viral_ratio >= VIRAL_THRESHOLD_OUTLIER:
        return "outlier"

    if viral_ratio >= VIRAL_THRESHOLD_NEUTRAL:
        return "average"

    return "subpar"


def clean_transcript_text(text: str) -> str:
    """Cleans transcript text by stripping extra whitespaces and newline characters."""
    if not text:
        return ""

    return " ".join(text.replace("\n", " ").split()).strip()
