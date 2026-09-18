from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel

from underfind.backend.schemas.video import VideoItem
from underfind.backend.schemas.idea import IdeaItem


class DashboardStats(BaseModel):
    cached_videos_count: int
    max_viral_ratio: float
    avg_viral_ratio: Optional[float] = 0.0
    total_queries_saved: int
    estimated_hook_score: Optional[float] = 88.5
    ideas_total: int
    ideas_backlog: int
    ideas_in_progress: int
    ideas_done: int
    top_outliers: Optional[List[VideoItem]] = None
    recent_ideas: Optional[List[IdeaItem]] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    youtube_api_configured: bool
