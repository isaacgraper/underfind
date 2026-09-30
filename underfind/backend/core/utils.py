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


_YOUTUBE_ID = r"(?P<id>[A-Za-z0-9_-]{11})"
_SOURCE_URL_PATTERNS = [
    ("youtube", re.compile(r"^https?://(?:www\.|m\.)?youtube\.com/(?:shorts|embed|live)/" + _YOUTUBE_ID)),
    ("youtube", re.compile(r"^https?://(?:www\.|m\.)?youtube\.com/watch\?(?:.*&)?v=" + _YOUTUBE_ID)),
    ("youtube", re.compile(r"^https?://youtu\.be/" + _YOUTUBE_ID)),
    ("instagram", re.compile(r"^https?://(?:www\.)?instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:reels?|p|tv)/(?P<id>[A-Za-z0-9_-]+)")),
    ("tiktok", re.compile(r"^https?://(?:www\.|m\.)?tiktok\.com/@[^/]+/(?:video|photo)/(?P<id>\d+)")),
]
_TIKTOK_SHORT_LINK = re.compile(r"^https?://(?:vm\.tiktok\.com|vt\.tiktok\.com|(?:www\.)?tiktok\.com/t)/[A-Za-z0-9]+")


def is_tiktok_short_link(url: str) -> bool:
    """True for vm.tiktok.com / tiktok.com/t/ links that must be resolved via redirect first."""
    return bool(_TIKTOK_SHORT_LINK.match((url or "").strip()))


def parse_source_url(url: str) -> tuple[str, str]:
    """Extracts (platform, source_id) from a YouTube, Instagram or TikTok video URL."""
    clean = (url or "").strip()

    for platform, pattern in _SOURCE_URL_PATTERNS:
        match = pattern.match(clean)

        if match:
            return platform, match.group("id")

    if is_tiktok_short_link(clean):
        raise ValueError(f"TikTok short link must be resolved before parsing: {clean}")

    raise ValueError(f"Unsupported or unrecognized video URL: {clean}")


def hamming_distance_hex(
    hash_a: str,
    hash_b: str,
) -> int:
    """Bit distance between two equal-length hex perceptual hashes."""
    if len(hash_a) != len(hash_b):
        raise ValueError("Perceptual hashes must have the same length")

    return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")
