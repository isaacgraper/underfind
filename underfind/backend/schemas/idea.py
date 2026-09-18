from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from underfind.backend.core.constants import DEFAULT_IDEA_STATUS
from underfind.backend.schemas.video import VideoItem


class IdeaItem(BaseModel):
    id: Optional[int] = None
    video_id: str
    title: str
    channel_title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    views: Optional[int] = 0
    subscribers: Optional[int] = 0
    viral_ratio: Optional[float] = 0.0
    duration_seconds: Optional[int] = 0
    video_url: Optional[str] = None
    status: str = DEFAULT_IDEA_STATUS
    hook_text: Optional[str] = None
    script_notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SaveIdeaRequest(BaseModel):
    video: VideoItem
    status: str = DEFAULT_IDEA_STATUS
    hook_text: Optional[str] = ""
    notes: Optional[str] = ""


class UpdateIdeaRequest(BaseModel):
    status: str
    notes: Optional[str] = None
