from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from underfind.backend.core.constants import DEFAULT_MODELING_TONE


class TranscriptLine(BaseModel):
    text: str
    start: float
    duration: float


class VideoBlueprint(BaseModel):
    video_id: str
    title: str
    channel_title: str
    views: int
    subscribers: int
    viral_ratio: float
    video_url: str
    duration_seconds: int
    is_short: bool
    hook_text: str = Field(description="First 3-5 seconds transcript text (Opening Hook)")
    hook_duration: float
    full_transcript: str
    transcript_segments: List[TranscriptLine] = Field(default_factory=list)
    key_takeaways: List[str] = Field(default_factory=list)
    suggested_prompt: str = Field(description="Ready-to-use LLM prompt to model and adapt this video")


class ModelingPromptRequest(BaseModel):
    video_id: str
    target_niche: Optional[str] = None
    audience: Optional[str] = None
    tone: Optional[str] = DEFAULT_MODELING_TONE
