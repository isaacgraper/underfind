from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends

from underfind.backend.schemas.blueprint import VideoBlueprint, ModelingPromptRequest
from underfind.backend.services.youtube_service import YouTubeService
from underfind.backend.services.transcript_service import TranscriptService
from underfind.backend.db.database import CacheManager
from underfind.backend.dependencies import get_youtube_service, get_cache_manager
from underfind.backend.core.logger import logger

router = APIRouter(tags=["Blueprints & Hook Dissection"])


@router.get("/blueprint/{video_id}", response_model=VideoBlueprint)
def get_video_blueprint(
    video_id: str,
    target_niche: Optional[str] = Query(None, description="Custom creator niche to adapt the script into"),
    svc: YouTubeService = Depends(get_youtube_service),
    db: CacheManager = Depends(get_cache_manager),
) -> VideoBlueprint:
    """Dissects the opening hook (0-3s), extracts timestamped transcript, and generates modeling prompt."""
    logger.debug("API /api/blueprint/%s requested (niche: %s)", video_id, target_niche)

    cached_bp = db.get_cached_blueprint(video_id)
    if cached_bp:
        logger.trace("API returning cached blueprint for video %s", video_id)
        return cached_bp

    video = svc.get_video_by_id(video_id)
    if not video:
        logger.warning("API blueprint target video %s not found", video_id)
        raise HTTPException(status_code=404, detail=f"Video with ID '{video_id}' not found.")

    blueprint = TranscriptService.create_blueprint(video, custom_niche=target_niche)
    db.save_blueprint(blueprint)

    logger.trace("API generated and saved blueprint for video %s", video_id)
    return blueprint


@router.post("/blueprint/prompt")
def generate_custom_prompt(
    req: ModelingPromptRequest,
    svc: YouTubeService = Depends(get_youtube_service),
) -> dict:
    """Generates an LLM script engineering prompt tailored for a specific audience and tone."""
    logger.debug("API /api/blueprint/prompt requested for video %s", req.video_id)
    video = svc.get_video_by_id(req.video_id)

    if not video:
        raise HTTPException(status_code=404, detail=f"Video '{req.video_id}' not found.")

    segments = TranscriptService.get_transcript(req.video_id) or []
    full_text = " ".join(s.text for s in segments) if segments else (video.description or "")
    hook_text, _ = TranscriptService.extract_hook(segments)

    prompt = TranscriptService.generate_modeling_prompt(
        req=req,
        video=video,
        hook=hook_text or "Visual hook",
        transcript=full_text,
    )

    logger.trace("Generated custom prompt for video %s", req.video_id)
    return {
        "video_id": req.video_id,
        "target_niche": req.target_niche,
        "tone": req.tone,
        "prompt": prompt,
    }
