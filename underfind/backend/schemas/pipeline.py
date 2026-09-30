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
    has_onscreen_text: Optional[bool] = None

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
    tts_voice: Optional[str] = Field(default=None, description="TTS voice for dub mode; defaults by language")
    auto_approve_translation: bool = Field(default=False, description="Skip the translation review gate for this page")
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
    attempts: int = 0
    locked_by: Optional[str] = None
    translation_approved: bool = False
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


class TranscriptWord(BaseModel):
    start: float
    end: float
    word: str
    probability: Optional[float] = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    words: List[TranscriptWord] = Field(default_factory=list)


class OnScreenText(BaseModel):
    at_seconds: float
    text: str
    confidence: float


class Transcript(BaseModel):
    language: Optional[str] = None
    language_probability: Optional[float] = None
    duration_seconds: Optional[float] = None
    model: Optional[str] = None
    segments: List[TranscriptSegment] = Field(default_factory=list)
    onscreen_text: Optional[List[OnScreenText]] = Field(
        default=None,
        description="Burned-in text found by OCR sampling; None when OCR is not installed",
    )

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments).strip()

    @property
    def has_speech(self) -> bool:
        return any(s.text.strip() for s in self.segments)


class RunJobRequest(BaseModel):
    until_blocked: bool = Field(default=True, description="Keep advancing until a stage without a handler or a review gate")


class TranslatedSegment(BaseModel):
    index: int
    start: float
    end: float
    source_text: str
    text: str
    max_chars: int = Field(description="Length budget so the line can be read (subtitles) or spoken (dub) within the segment")

    @property
    def over_budget(self) -> bool:
        return len(self.text) > self.max_chars


class TranslatedOnScreenText(BaseModel):
    source: str
    text: str


class Translation(BaseModel):
    source_language: Optional[str] = None
    target_language: str
    page_id: int
    mode: str
    model: Optional[str] = None
    segments: List[TranslatedSegment] = Field(default_factory=list)
    caption: str = ""
    hashtags: List[str] = Field(default_factory=list)
    onscreen_text: List[TranslatedOnScreenText] = Field(default_factory=list)
    approved: bool = False
    approved_at: Optional[str] = None
    edited: bool = False


class SegmentEdit(BaseModel):
    index: int
    text: str


class UpdateTranslationRequest(BaseModel):
    segments: Optional[List[SegmentEdit]] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    approve: Optional[bool] = None
