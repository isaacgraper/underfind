from __future__ import annotations

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from underfind.backend.schemas.idea import IdeaItem, SaveIdeaRequest, UpdateIdeaRequest
from underfind.backend.db.database import CacheManager
from underfind.backend.dependencies import get_cache_manager
from underfind.backend.core.logger import logger

router = APIRouter(tags=["Ideas Kanban Pipeline"])


@router.get("/ideas", response_model=List[Dict[str, Any]])
def get_all_ideas(
    db: CacheManager = Depends(get_cache_manager),
) -> List[Dict[str, Any]]:
    """Lists all outlier ideas stored in the creator's Kanban production pipeline."""
    logger.debug("API GET /api/ideas requested")
    ideas = db.get_all_ideas()
    logger.trace("API returning %d Kanban ideas", len(ideas))
    return ideas


@router.post("/ideas", response_model=Dict[str, Any])
def save_new_idea(
    req: SaveIdeaRequest,
    db: CacheManager = Depends(get_cache_manager),
) -> Dict[str, Any]:
    """Adds a video outlier to the ideas Kanban board."""
    logger.debug("API POST /api/ideas for video %s (status: %s)", req.video.video_id, req.status)
    saved = db.save_idea(
        video=req.video,
        status=req.status,
        hook_text=req.hook_text or "",
        notes=req.notes or "",
    )
    logger.trace("API saved idea %s", req.video.video_id)
    return saved


@router.patch("/ideas/{video_id}")
def update_idea_status(
    video_id: str,
    req: UpdateIdeaRequest,
    db: CacheManager = Depends(get_cache_manager),
) -> dict:
    """Updates idea pipeline column status ('backlog' -> 'in_progress' -> 'done')."""
    logger.debug("API PATCH /api/ideas/%s to status '%s'", video_id, req.status)
    success = db.update_idea_status(
        video_id=video_id,
        new_status=req.status,
        notes=req.notes,
    )

    if not success:
        logger.warning("Idea %s not found for update", video_id)
        raise HTTPException(status_code=404, detail=f"Idea for video '{video_id}' not found.")

    logger.trace("API successfully updated idea %s to status %s", video_id, req.status)
    return {"status": "success", "video_id": video_id, "new_status": req.status}


@router.delete("/ideas/{video_id}")
def delete_idea(
    video_id: str,
    db: CacheManager = Depends(get_cache_manager),
) -> dict:
    """Deletes an idea card from the Kanban board."""
    logger.debug("API DELETE /api/ideas/%s", video_id)
    success = db.delete_idea(video_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Idea for video '{video_id}' not found.")

    logger.trace("API deleted idea %s", video_id)
    return {"status": "deleted", "video_id": video_id}
