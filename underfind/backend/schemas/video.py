from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field

from underfind.backend.core.constants import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_REGION,
    DEFAULT_ORDER,
    MIN_SUBSCRIBER_BASE,
)
from underfind.backend.core.utils import calculate_viral_ratio


class VideoItem(BaseModel):
    video_id: str
    title: str
    channel_id: Optional[str] = None
    channel_title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    views: Optional[int] = 0
    likes: Optional[int] = 0
    comments_count: Optional[int] = 0
    subscribers: Optional[int] = 0
    duration_seconds: Optional[int] = 0
    published_at: Optional[str] = None
    video_url: Optional[str] = None
    is_short: bool = False
    viral_ratio: float = Field(default=0.0, description="Views / max(Subscribers, 100) - measures viral breakout factor")
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    @classmethod
    def calculate_viral_ratio(
        cls,
        views: Optional[int],
        subscribers: Optional[int],
    ) -> float:
        return calculate_viral_ratio(views, subscribers, min_base=MIN_SUBSCRIBER_BASE)


class SearchRequest(BaseModel):
    query: str
    is_shorts_only: bool = False
    min_views: Optional[int] = None
    max_views: Optional[int] = None
    max_subscribers: Optional[int] = None
    min_viral_ratio: Optional[float] = None
    max_results: int = DEFAULT_MAX_RESULTS
    order: str = DEFAULT_ORDER
    published_after_days: Optional[int] = None
    region_code: str = DEFAULT_REGION
    force_refresh: bool = False


class TrendingRequest(BaseModel):
    region_code: str = DEFAULT_REGION
    category_id: Optional[str] = None
    shorts_only: bool = True
    max_results: int = DEFAULT_MAX_RESULTS
