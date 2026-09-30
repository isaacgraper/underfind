from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator

from underfind.backend.core.constants import (
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_LOCALIZATION_MODE,
)


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    LOCAL = "local"


class MediaType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    CAROUSEL = "carousel"


class Layout(str, Enum):
    AUTO = "auto"
    HEADLINE_CARD = "headline_card"
    LETTERBOX = "letterbox"
    FULL_BLEED = "full_bleed"


OUTPUT_KINDS: List[str] = ["reel", "post", "carousel"]


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
    media_type: Optional[MediaType] = None
    media_files: List[str] = Field(default_factory=list, description="Downloaded media file names inside the source folder, in post order")

    @property
    def key(self) -> str:
        return f"{self.platform.value}:{self.source_id}"


class RenderTemplate(BaseModel):
    """
    Visual style of a page's posts. Layouts, from the reference posts:
      headline_card  media on top, black card below with a brand tag between gradient lines and a big condensed
                     headline whose highlighted words (*like this*) get a gradient
      letterbox      media centered on the background, untouched (memes, infographics, AI art with baked-in labels)
      full_bleed     video fills the frame (trailers, gameplay), optional subtitles
      auto           headline_card when the source has a headline band, full_bleed for vertical video, else letterbox
    """

    id: Optional[int] = None
    name: str
    layout: Layout = Layout.AUTO
    width: int = 1080
    height: int = 1920
    post_height: int = 1350
    background_color: str = "#000000"
    font_path: Optional[str] = Field(default=None, description="TTF/OTF for headline and brand tag; bundled Anton when empty")
    headline_color: str = "#FFFFFF"
    headline_uppercase: bool = True
    highlight_colors: List[str] = Field(default_factory=lambda: ["#D946EF", "#FB923C"], description="Gradient for *highlighted* words")
    headline_max_font_size: int = 150
    headline_min_font_size: int = 64
    headline_max_lines: int = 5
    card_ratio: float = Field(default=0.36, ge=0.2, le=0.6, description="Share of the frame used by the headline card")
    brand_tag_font_size: int = 44
    brand_tag_colors: List[str] = Field(default_factory=lambda: ["#C026D3", "#F97316"])
    still_seconds: float = Field(default=8.0, ge=2.0, le=60.0, description="Reel length for image posts (per image in carousels)")
    ken_burns_zoom: float = Field(default=1.08, ge=1.0, le=1.5)
    video_fit: str = Field(default="fit", pattern="^(fit|fill)$")
    subtitle_font: str = "Anton"
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
    niche: Optional[str] = Field(default=None, description="Niche preset in config/niches/<name>.yaml (glossary, keywords, hashtags)")
    brand_tag: Optional[str] = Field(default=None, description="Text in the headline card's brand line; defaults to the handle in capitals")
    glossary: List[str] = Field(default_factory=list, description="Extra terms that must never be translated (on top of the niche's)")
    outputs: List[str] = Field(default_factory=lambda: ["reel"], description="Any of reel (9:16 video), post (4:5 image), carousel (4:5 images)")

    @field_validator("outputs")
    @classmethod
    def _valid_outputs(cls, value: List[str]) -> List[str]:
        unknown = [v for v in value if v not in OUTPUT_KINDS]

        if unknown or not value:
            raise ValueError(f"outputs must be a non-empty subset of {OUTPUT_KINDS}; got {value}")

        return list(dict.fromkeys(value))
    audio_bed_path: Optional[str] = Field(default=None, description="Audio for image reels; silent when empty (add trending audio when publishing)")
    auto_approve_translation: bool = Field(default=False, description="Skip the translation review gate for this page")
    local_only: bool = Field(default=True, description="Only local AI models for this page's jobs (checked by default)")
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
    local_only: Optional[bool] = Field(default=None, description="Per-job override of the page's local-only setting; None inherits")
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
    local_only: Optional[bool] = Field(default=None, description="Override the page's local-only setting for this job")


class UpdateJobStatusRequest(BaseModel):
    status: JobStatus
    note: Optional[str] = None
    error: Optional[str] = None


class AssignPageRequest(BaseModel):
    page_id: int


class SetLocalOnlyRequest(BaseModel):
    local_only: Optional[bool] = Field(description="True = local models only, False = online allowed (when AI_MODE=online), None = inherit from page")


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
    box: Optional[List[int]] = Field(default=None, description="[x0, y0, x1, y1] in media pixels")
    media_file: Optional[str] = None


class Headline(BaseModel):
    """Headline band detected in the source media (the part a modeled post re-types in its own card)."""

    text: str
    brand_text: Optional[str] = None
    media_file: Optional[str] = None
    region: Optional[List[int]] = Field(default=None, description="[x0, y0, x1, y1] covering the brand tag and headline lines")
    position: Optional[str] = Field(default=None, description="top | bottom when the band spans the media width and can be cropped away")
    media_size: Optional[List[int]] = None


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
    headline: Optional[Headline] = None

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
    local: bool = True
    source_language: Optional[str] = None
    target_language: str
    page_id: int
    mode: str
    model: Optional[str] = None
    segments: List[TranslatedSegment] = Field(default_factory=list)
    headline: str = Field(default="", description="Translated headline for the card; *word* marks gradient highlights")
    headline_source: str = ""
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
    headline: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    approve: Optional[bool] = None


class CreateJobFromFilesRequest(BaseModel):
    """Local media already on this machine (saved posts, your own material)."""

    files: List[str] = Field(min_length=1)
    source_url: Optional[str] = Field(default=None, description="Original post URL, for credit and the used-source registry")
    caption: Optional[str] = None
    author_handle: Optional[str] = None
    page_id: Optional[int] = None
    mode: str = Field(default=DEFAULT_LOCALIZATION_MODE, pattern="^(subtitles|dub)$")
    force: bool = False
    local_only: Optional[bool] = None
