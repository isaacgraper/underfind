from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict
from fastapi import APIRouter, BackgroundTasks, Depends, Query

from underfind.backend.core.errors import InvalidTransitionError, NotFoundError
from underfind.backend.core.logger import logger
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo, get_pipeline_runner
from underfind.backend.schemas.pipeline import (
    AssignPageRequest,
    CreateJobFromUrlRequest,
    Job,
    JobEvent,
    JobStatus,
    RunJobRequest,
    SetLocalOnlyRequest,
    Transcript,
    Translation,
    UpdateJobStatusRequest,
    UpdateTranslationRequest,
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
    return JobService(repo).open_job_from_url(req.url, page_id=req.page_id, mode=req.mode, force=req.force, local_only=req.local_only)


@router.post("/jobs/from-video", response_model=Job)
def create_job_from_video(
    video: VideoItem,
    page_id: Optional[int] = Query(None),
    mode: str = Query("subtitles", pattern="^(subtitles|dub)$"),
    force: bool = Query(False),
    local_only: Optional[bool] = Query(None, description="Override the page's local-only setting for this job"),
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Job:
    """Opens a localization job from a search/trending result, keeping its YouTube metadata."""
    logger.debug("API POST /api/jobs/from-video video=%s page=%s local_only=%s", video.video_id, page_id, local_only)
    service = JobService(repo)
    return service.open_job(service.source_from_video_item(video), page_id=page_id, mode=mode, force=force, local_only=local_only)


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


@router.patch("/jobs/{job_id}/local-only", response_model=Job)
def set_job_local_only(
    job_id: str,
    req: SetLocalOnlyRequest,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Job:
    """Per-job "local only" switch: true/false overrides the page, null inherits it. Online needs AI_MODE=online."""
    return repo.set_local_only(job_id, req.local_only)


@router.post("/jobs/{job_id}/run", status_code=202)
def run_job(
    job_id: str,
    background: BackgroundTasks,
    req: Optional[RunJobRequest] = None,
    repo: PipelineRepository = Depends(get_pipeline_repo),
    runner=Depends(get_pipeline_runner),
) -> dict:
    """Runs the job's automated stages (download, transcribe, ...) in the background."""
    job = repo.get_job(job_id)
    until_blocked = req.until_blocked if req else True
    background.add_task(runner.run_until_blocked if until_blocked else runner.run_next, job_id)
    logger.debug("API POST /api/jobs/%s/run scheduled from status '%s'", job_id, job.status.value)
    return {"status": "scheduled", "job_id": job_id, "from_status": job.status.value}


@router.post("/pipeline/tick", status_code=202)
def pipeline_tick(
    background: BackgroundTasks,
    limit: int = Query(20, ge=1, le=200),
    runner=Depends(get_pipeline_runner),
) -> dict:
    """Processes every runnable job once in the background (what the worker does on each poll)."""
    background.add_task(runner.tick, limit)
    return {"status": "scheduled", "limit": limit}


@router.get("/jobs/{job_id}/transcript", response_model=Transcript)
def get_job_transcript(
    job_id: str,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Transcript:
    job = repo.get_job(job_id)
    path = job.artifacts.get("transcript")

    if not path or not Path(path).exists():
        raise NotFoundError(f"Job '{job_id}' has no transcript yet (status '{job.status.value}').")

    return Transcript.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _translation_file(job: Job) -> Path:
    path = job.artifacts.get("translation")

    if not path or not Path(path).exists():
        raise NotFoundError(f"Job '{job.id}' has no translation yet (status '{job.status.value}').")

    return Path(path)


@router.get("/jobs/{job_id}/translation", response_model=Translation)
def get_job_translation(
    job_id: str,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Translation:
    """Source and translated lines side by side, with the localized caption and hashtags, for review."""
    job = repo.get_job(job_id)
    return Translation.model_validate_json(_translation_file(job).read_text(encoding="utf-8"))


@router.put("/jobs/{job_id}/translation", response_model=Translation)
def update_job_translation(
    job_id: str,
    req: UpdateTranslationRequest,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Translation:
    """Edits translated lines, caption or hashtags while the job waits at review; optionally approves in the same call."""
    job = repo.get_job(job_id)

    if job.status != JobStatus.TRANSLATED:
        raise InvalidTransitionError(f"Translation can only be edited while the job is 'translated' (now '{job.status.value}').")

    path = _translation_file(job)
    translation = Translation.model_validate_json(path.read_text(encoding="utf-8"))

    if req.segments:
        by_index = {s.index: s for s in translation.segments}
        unknown = [e.index for e in req.segments if e.index not in by_index]

        if unknown:
            raise ValueError(f"Unknown segment indexes: {unknown}")

        for edit in req.segments:
            by_index[edit.index].text = edit.text.strip()

        translation.edited = True

    if req.caption is not None:
        translation.caption = req.caption.strip()
        translation.edited = True

    if req.hashtags is not None:
        translation.hashtags = ["#" + t.strip().lstrip("#") for t in req.hashtags if t.strip().lstrip("#")]
        translation.edited = True

    if req.approve is not None:
        translation.approved = req.approve
        translation.approved_at = datetime.now(timezone.utc).isoformat() if req.approve else None

    path.write_text(json.dumps(translation.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    repo.set_translation_approved(job_id, translation.approved)
    logger.debug("API PUT /api/jobs/%s/translation (approved=%s, edited=%s)", job_id, translation.approved, translation.edited)
    return translation


@router.post("/jobs/{job_id}/translation/approve", response_model=Translation)
def approve_job_translation(
    job_id: str,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> Translation:
    """Opens the review gate: the worker picks the job up for voicing on its next poll."""
    return update_job_translation(job_id, UpdateTranslationRequest(approve=True), repo)
