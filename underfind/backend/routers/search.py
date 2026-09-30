from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends

from underfind.backend.core.constants import (
    DEFAULT_REGION,
    DEFAULT_MIN_VIEWS,
    DEFAULT_MAX_SUBSCRIBERS,
    DEFAULT_MIN_VIRAL_RATIO,
    DEFAULT_MAX_RESULTS,
    DEFAULT_ORDER_OUTLIERS,
)
from underfind.backend.schemas.video import VideoItem, SearchRequest
from underfind.backend.services.youtube_service import YouTubeService
from underfind.backend.dependencies import get_youtube_service
from underfind.backend.core.errors import QuotaExceededError
from underfind.backend.core.logger import logger

router = APIRouter(tags=["Search & Outliers"])


@router.post("/search", response_model=List[VideoItem])
def search_videos(
    req: SearchRequest,
    svc: YouTubeService = Depends(get_youtube_service),
) -> List[VideoItem]:
    """Executes a structured search query with SQLite caching and advanced filtering."""
    logger.debug("API /api/search received request: query='%s', shorts=%s", req.query, req.is_shorts_only)

    try:
        results = svc.search(req)
        logger.trace("API /api/search returning %d videos", len(results))
        return results
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except TimeoutError as te:
        raise HTTPException(status_code=504, detail=str(te))
    except QuotaExceededError:
        raise
    except Exception as e:
        logger.error("Error in API /api/search: %s", e)
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.get("/shorts/outliers", response_model=List[VideoItem])
def get_shorts_outliers(
    q: str = Query(..., description="Target search query or creator niche"),
    max_subscribers: Optional[int] = Query(DEFAULT_MAX_SUBSCRIBERS, description="Upper subscriber threshold"),
    min_views: Optional[int] = Query(DEFAULT_MIN_VIEWS, description="Minimum views threshold"),
    min_viral_ratio: Optional[float] = Query(DEFAULT_MIN_VIRAL_RATIO, description="Minimum viral multiplier threshold"),
    region_code: str = Query(DEFAULT_REGION, description="Target country ISO code"),
    limit: int = Query(DEFAULT_MAX_RESULTS, description="Maximum results limit"),
    force_refresh: bool = Query(False, description="Bypass local cache"),
    svc: YouTubeService = Depends(get_youtube_service),
) -> List[VideoItem]:
    """Discovers vertical short-form outliers in a specific niche."""
    logger.debug("API /api/shorts/outliers received query: '%s' in region '%s'", q, region_code)

    req = SearchRequest(
        query=f"{q} #shorts",
        is_shorts_only=True,
        min_views=min_views,
        max_subscribers=max_subscribers,
        min_viral_ratio=min_viral_ratio,
        max_results=limit,
        order=DEFAULT_ORDER_OUTLIERS,
        region_code=region_code,
        force_refresh=force_refresh,
    )

    try:
        results = svc.search(req)
        logger.trace("API /api/shorts/outliers returning %d outlier videos", len(results))
        return results
    except QuotaExceededError:
        raise
    except Exception as e:
        logger.error("Error in API /api/shorts/outliers: %s", e)
        raise HTTPException(status_code=500, detail=f"Outliers query failed: {str(e)}")


@router.get("/video/{video_id}", response_model=VideoItem)
def get_video_details(
    video_id: str,
    svc: YouTubeService = Depends(get_youtube_service),
) -> VideoItem:
    """Retrieves full metadata for a single video including views, likes, comments, tags, and description."""
    logger.debug("API /api/video/%s requested", video_id)

    video = svc.get_video_by_id(video_id)

    if not video:
        logger.warning("API video %s not found", video_id)
        raise HTTPException(status_code=404, detail=f"Video with ID '{video_id}' not found.")

    logger.trace("API returning video %s metadata", video_id)
    return video
