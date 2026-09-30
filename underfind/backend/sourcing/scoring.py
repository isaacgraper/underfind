from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from underfind.backend.core.niches import Niche
from underfind.backend.schemas.pipeline import SourceVideo

# Platforms that don't expose views to third parties (Instagram Business Discovery) get an estimate from likes.
LIKES_TO_VIEWS = 25
MIN_AGE_HOURS = 1.0


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _log_score(value: float, target: float) -> float:
    """0 at 0, 1 at target, log-scaled so 10x below target still scores (viral posts span orders of magnitude)."""
    if value <= 0:
        return 0.0

    return max(0.0, min(1.0, math.log10(value + 1) / math.log10(target + 1)))


def _text(source: SourceVideo) -> str:
    return " ".join(filter(None, [source.title, source.caption])).lower()


def _matches(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", text) is not None


def estimated_views(source: SourceVideo) -> Tuple[Optional[float], bool]:
    """(views, estimated?) using real views when known, else likes x LIKES_TO_VIEWS."""
    if source.views:
        return float(source.views), False

    if source.likes:
        return float(source.likes * LIKES_TO_VIEWS), True

    return None, False


def score_candidate(
    source: SourceVideo,
    niche: Niche,
    now: Optional[datetime] = None,
    seed: bool = False,
) -> Tuple[float, Dict[str, float], Optional[str]]:
    """
    Returns (score 0-100, component scores 0-1, rejection reason or None).
      velocity   views per hour since publishing, vs scoring.target_views_per_hour
      ratio      views / followers (breakout vs the account's size), vs scoring.target_ratio
      engagement (likes + comments) / views, vs scoring.target_engagement
      relevance  niche keywords in title/caption (full marks when the niche has no keywords)
    Exclude keywords, age and duration limits reject outright; missing metrics score a neutral 0.5.
    seed=True (posts from the niche's own seed pages) counts as fully relevant: those pages are on-topic by choice.
    """
    now = now or datetime.now(timezone.utc)
    text = _text(source)
    include = niche.keywords.include
    exclude = [k for k in niche.keywords.exclude if _matches(text, k)]

    if exclude:
        return 0.0, {}, f"auto: excluded keyword '{exclude[0]}'"

    published = _parse_time(source.published_at)

    if published and (now - published).days > niche.scan.max_age_days:
        return 0.0, {}, f"auto: older than {niche.scan.max_age_days} days"

    if source.duration_seconds and source.duration_seconds > niche.scan.max_duration_seconds:
        return 0.0, {}, f"auto: longer than {niche.scan.max_duration_seconds}s"

    views, _estimated = estimated_views(source)
    cfg = niche.scoring
    scores: Dict[str, float] = {}

    if views is not None and published:
        hours = max(MIN_AGE_HOURS, (now - published).total_seconds() / 3600)
        scores["velocity"] = _log_score(views / hours, cfg.target_views_per_hour)
    else:
        scores["velocity"] = 0.5

    scores["ratio"] = _log_score(views / max(source.followers, 1), cfg.target_ratio) if views is not None and source.followers else 0.5

    if views:
        engagement = ((source.likes or 0) + (source.comments_count or 0)) / views
        scores["engagement"] = min(1.0, engagement / cfg.target_engagement) if (source.likes or source.comments_count) else 0.5
    else:
        scores["engagement"] = 0.5

    if include and not seed:
        hits = sum(1 for k in include if _matches(text, k))
        scores["relevance"] = min(1.0, hits / 2)
    else:
        scores["relevance"] = 1.0

    weights = {k: v for k, v in cfg.weights.items() if k in scores and v > 0}
    total = sum(weights.values()) or 1.0
    score = round(100 * sum(scores[k] * w for k, w in weights.items()) / total, 1)
    scores = {k: round(v, 3) for k, v in scores.items()}

    if include and not seed and scores["relevance"] == 0:
        return score, scores, "auto: no niche keyword in title or caption"

    if score < cfg.min_score:
        return score, scores, f"auto: score below {cfg.min_score:g}"

    return score, scores, None
