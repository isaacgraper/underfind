from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from underfind.backend.core.constants import (
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_LOCALIZATION_MODE,
)


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class JobStatus(str, Enum):
    FOUND = "found"
    DOWNLOADED = "downloaded"
    TRANSCRIBED = "transcribed"
    TRANSLATED = "translated"
    VOICED = "voiced"
    RENDERED = "rendered"
    EXPORTED = "exported"
    FAILED = "failed"
    DISCARDED = "discarded"


PIPELINE_STAGES: List[JobStatus] = [
    JobStatus.FOUND,
    JobStatus.DOWNLOADED,
    JobStatus.TRANSCRIBED,
    JobStatus.TRANSLATED,
    JobStatus.VOICED,
    JobStatus.RENDERED,
    JobStatus.EXPORTED,
]

# Stages from this point on produce page-specific output and need a target page.
PAGE_REQUIRED_FROM: JobStatus = JobStatus.TRANSLATED


class SourceVideo(BaseModel):
    platform: Platform
    source_id: str
    url: str
    title: Optional[str] = None
    caption: Optional[str] = None
    author_handle: Optional[str] = None
    author_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments_count: Optional[int] = None
    followers: Optional[int] = None
    duration_seconds: Optional[int] = None
    published_at: Optional[str] = None
    language: Optional[str] = None
    phash: Optional[str] = Field(default=None, description="64-bit perceptual hash (hex) of a reference frame")

    @property
    def key(self) -> str:
        return f"{self.platform.value}:{self.source_id}"


class RenderTemplate(BaseModel):
    id: Optional[int] = None
    name: str
    width: int = 1080
    height: int = 1920
    background_color: str = "#000000"
    header_height: int = 260
    avatar_size: int = 140
    name_font: str = "Inter-Bold"
    name_font_size: int = 52
    name_color: str = "#FFFFFF"
    handle_font_size: int = 38
    handle_color: str = "#A1A1AA"
    show_verified_badge: bool = True
    video_fit: str = Field(default="fit", pattern="^(fit|fill)$")
    subtitle_font: str = "Inter-Bold"
    subtitle_font_size: int = 64
    subtitle_color: str = "#FFFFFF"
    subtitle_outline_color: str = "#000000"
    subtitle_position_y: float = Field(default=0.72, ge=0.0, le=1.0)


class PageProfile(BaseModel):
    id: Optional[int] = None
    display_name: str
    handle: str
    avatar_path: Optional[str] = None
    language: str = DEFAULT_TARGET_LANGUAGE
    template_id: Optional[int] = None
    default_hashtags: List[str] = Field(default_factory=list)
    caption_footer: Optional[str] = None
    active: bool = True


class Job(BaseModel):
    id: str
    source_key: str
    page_id: Optional[int] = None
    status: JobStatus = JobStatus.FOUND
    failed_from: Optional[JobStatus] = None
    error: Optional[str] = None
    mode: str = DEFAULT_LOCALIZATION_MODE
    artifacts: Dict[str, str] = Field(default_factory=dict)
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source: Optional[SourceVideo] = None


class JobEvent(BaseModel):
    job_id: str
    from_status: Optional[JobStatus] = None
    to_status: JobStatus
    note: Optional[str] = None
    created_at: str


class CreateJobFromUrlRequest(BaseModel):
    url: str
    page_id: Optional[int] = None
    mode: str = Field(default=DEFAULT_LOCALIZATION_MODE, pattern="^(subtitles|dub)$")
    force: bool = Field(default=False, description="Create even if the source was already used")


class UpdateJobStatusRequest(BaseModel):
    status: JobStatus
    note: Optional[str] = None
    error: Optional[str] = None


class AssignPageRequest(BaseModel):
    page_id: int


class QuotaStatus(BaseModel):
    provider: str
    day: str
    used: int
    limit: int
    remaining: int
    exhausted: bool
