from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from underfind.backend.schemas.pipeline import SourceVideo


class CandidateStatus(str, Enum):
    NEW = "new"            # scored, waiting for a decision
    QUEUED = "queued"      # turned into job(s)
    REJECTED = "rejected"  # filtered out (off-topic, too old/long, low score) or rejected by hand
    SKIPPED = "skipped"    # already used by an earlier job


class Candidate(BaseModel):
    id: Optional[int] = None
    source_key: str
    niche: str
    scanner: str = Field(description="Where it came from: youtube_keywords, youtube_channel:<id>, instagram:<user>, tiktok:<user>, external")
    score: float = 0.0
    scores: Dict[str, float] = Field(default_factory=dict, description="Component scores 0-1: velocity, ratio, engagement, relevance")
    status: CandidateStatus = CandidateStatus.NEW
    reason: Optional[str] = None
    job_ids: List[str] = Field(default_factory=list)
    discovered_at: Optional[str] = None
    updated_at: Optional[str] = None
    source: Optional[SourceVideo] = None


class ScanReport(BaseModel):
    id: Optional[int] = None
    niche: str
    started_at: str
    finished_at: Optional[str] = None
    found: int = 0
    new: int = 0
    rejected: int = 0
    skipped: int = 0
    queued: int = 0
    dry_run: bool = False
    errors: Dict[str, str] = Field(default_factory=dict, description="Scanner name -> error; other scanners still ran")
    top: List[Candidate] = Field(default_factory=list, description="Best new candidates of this scan")


class IngestCandidateRequest(BaseModel):
    """A candidate found elsewhere (vidIQ in a Claude routine, n8n, a browser extension)."""

    url: str
    niche: str
    title: Optional[str] = None
    caption: Optional[str] = None
    author_handle: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments_count: Optional[int] = None
    followers: Optional[int] = None
    duration_seconds: Optional[int] = None
    published_at: Optional[str] = None
    scanner: str = "external"


class QueueCandidateRequest(BaseModel):
    page_ids: Optional[List[int]] = Field(default=None, description="Target pages; default: every active page of the candidate's niche")
    mode: str = Field(default="subtitles", pattern="^(subtitles|dub)$")
    local_only: Optional[bool] = None


class RejectCandidateRequest(BaseModel):
    reason: Optional[str] = None
