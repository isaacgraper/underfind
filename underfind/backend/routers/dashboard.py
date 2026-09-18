from __future__ import annotations

import os
from typing import Optional
from fastapi import APIRouter, Query, Depends

from underfind.backend.core.constants import (
    DEFAULT_SHOWCASE_LIMIT,
    SERVICE_NAME,
    SERVICE_VERSION,
    DEFAULT_BENCHMARK_HOOK_SCORE,
)
from underfind.backend.schemas.stats import DashboardStats, HealthResponse
from underfind.backend.db.database import CacheManager
from underfind.backend.dependencies import get_cache_manager
from underfind.backend.core.logger import logger

router = APIRouter(tags=["Dashboard & Health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Returns API health status and whether YouTube API credentials are configured."""
    has_key = bool(os.environ.get("YOUTUBE_API_KEY") or os.environ.get("YOUTUBE_ANALYTICS_API_KEY"))
    return HealthResponse(
        status="healthy",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        youtube_api_configured=has_key,
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    limit: int = Query(DEFAULT_SHOWCASE_LIMIT, description="Number of top outliers for showcase"),
    db: CacheManager = Depends(get_cache_manager),
) -> DashboardStats:
    """Returns rich aggregate analytics, KPIs, ideas pipeline counts, and top outliers for the dashboard."""
    logger.debug("API GET /api/dashboard/stats requested (showcase limit: %d)", limit)

    with db._get_connection() as conn:
        video_stats = conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(viral_ratio), 0.0), COALESCE(AVG(viral_ratio), 0.0) FROM videos"
        ).fetchone()
        cached_count = video_stats[0]
        max_ratio = float(video_stats[1])
        avg_ratio = round(float(video_stats[2]), 1)

        queries_saved = conn.execute("SELECT COUNT(*) FROM search_queries").fetchone()[0]

        idea_rows = conn.execute("SELECT status, COUNT(*) FROM ideas_board GROUP BY status").fetchall()
        status_counts = {row[0]: row[1] for row in idea_rows}

    total_ideas = sum(status_counts.values())
    backlog_count = status_counts.get("backlog", 0)
    in_prog_count = status_counts.get("in_progress", 0)
    done_count = status_counts.get("done", 0)

    top_videos = db.get_top_performing_videos(limit=limit)
    raw_ideas = db.get_all_ideas()
    recent_ideas = [db.get_all_ideas() and raw_ideas[0]] if raw_ideas else []

    stats = DashboardStats(
        cached_videos_count=cached_count,
        max_viral_ratio=round(max_ratio, 1),
        avg_viral_ratio=avg_ratio,
        total_queries_saved=queries_saved,
        estimated_hook_score=DEFAULT_BENCHMARK_HOOK_SCORE,
        ideas_total=total_ideas,
        ideas_backlog=backlog_count,
        ideas_in_progress=in_prog_count,
        ideas_done=done_count,
        top_outliers=top_videos,
        recent_ideas=None,
    )

    logger.trace("API returning dashboard stats: %d cached videos, %.1fx peak viral", cached_count, max_ratio)
    return stats
