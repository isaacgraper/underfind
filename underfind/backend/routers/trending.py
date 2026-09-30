from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends

from underfind.backend.core.constants import DEFAULT_REGION, DEFAULT_MAX_RESULTS
from underfind.backend.schemas.video import VideoItem, TrendingRequest
from underfind.backend.services.youtube_service import YouTubeService
from underfind.backend.dependencies import get_youtube_service
from underfind.backend.core.errors import QuotaExceededError
from underfind.backend.core.logger import logger

router = APIRouter(tags=["Trending"])


@router.get("/trending", response_model=List[VideoItem])
def get_trending_videos(
    region_code: str = Query(DEFAULT_REGION, description="Country ISO code"),
    category_id: Optional[str] = Query(None, description="YouTube Video Category ID"),
    shorts_only: bool = Query(True, description="Filter for vertical short-form format"),
    limit: int = Query(DEFAULT_MAX_RESULTS, description="Number of results"),
    svc: YouTubeService = Depends(get_youtube_service),
) -> List[VideoItem]:
    """Retrieves real-time trending videos and Shorts for a target country."""
    logger.debug("API /api/trending requested for region '%s' (shorts_only=%s)", region_code, shorts_only)

    req = TrendingRequest(
        region_code=region_code,
        category_id=category_id,
        shorts_only=shorts_only,
        max_results=limit,
    )

    try:
        results = svc.get_trending(req)
        logger.trace("API /api/trending returning %d items", len(results))
        return results
    except QuotaExceededError:
        raise
    except Exception as e:
        logger.error("Error in API /api/trending: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending videos: {str(e)}")
