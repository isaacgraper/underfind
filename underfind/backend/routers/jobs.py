from __future__ import annotations

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Query

from underfind.backend.core.logger import logger
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo
from underfind.backend.schemas.pipeline import (
    AssignPageRequest,
    CreateJobFromUrlRequest,
    Job,
    JobEvent,
    JobStatus,
    UpdateJobStatusRequest,
)
from underfind.backend.schemas.video import VideoItem
from underfind.backend.services.job_service import JobService

router = APIRouter(tags=["Localization Jobs"])


@router.post("/jobs", response_model=Job)
def create_job_from_url(
    req: CreateJobFromUrlRequest,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Job:
    """Opens a localization job from a YouTube, Instagram or TikTok video URL."""
    logger.debug("API POST /api/jobs url='%s' page=%s mode=%s", req.url, req.page_id, req.mode)
    return JobService(repo).open_job_from_url(req.url, page_id=req.page_id, mode=req.mode, force=req.force)


@router.post("/jobs/from-video", response_model=Job)
def create_job_from_video(
    video: VideoItem,
    page_id: Optional[int] = Query(None),
    mode: str = Query("subtitles", pattern="^(subtitles|dub)$"),
    force: bool = Query(False),
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Job:
    """Opens a localization job from a search/trending result, keeping its YouTube metadata."""
    logger.debug("API POST /api/jobs/from-video video=%s page=%s", video.video_id, page_id)
    service = JobService(repo)
    return service.open_job(service.source_from_video_item(video), page_id=page_id, mode=mode, force=force)


@router.get("/jobs", response_model=List[Job])
def list_jobs(
    status: Optional[JobStatus] = Query(None),
    page_id: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> List[Job]:
    return repo.list_jobs(status=status, page_id=page_id, limit=limit)


@router.get("/jobs/stats", response_model=Dict[str, int])
def job_counts(
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Dict[str, int]:
    """Job counts per pipeline status."""
    return repo.count_jobs_by_status()


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(
    job_id: str,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Job:
    return repo.get_job(job_id)


@router.get("/jobs/{job_id}/events", response_model=List[JobEvent])
def get_job_events(
    job_id: str,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> List[JobEvent]:
    repo.get_job(job_id)
    return repo.get_job_events(job_id)


@router.patch("/jobs/{job_id}/status", response_model=Job)
def update_job_status(
    job_id: str,
    req: UpdateJobStatusRequest,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Job:
    """Moves a job through the pipeline (advance one stage, re-run an earlier one, fail, discard or restore)."""
    logger.debug("API PATCH /api/jobs/%s/status -> %s", job_id, req.status.value)
    return repo.transition(job_id, req.status, note=req.note, error=req.error)


@router.patch("/jobs/{job_id}/page", response_model=Job)
def assign_job_page(
    job_id: str,
    req: AssignPageRequest,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Job:
    return repo.assign_page(job_id, req.page_id)
