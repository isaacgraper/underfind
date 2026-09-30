from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

from underfind.backend.core.constants import JOBS_DIR, SOURCES_DIR, PHASH_FRAME_SECONDS
from underfind.backend.core.errors import DuplicateSourceError, PermanentStageError
from underfind.backend.core.logger import logger
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.pipeline.download import YtDlpDownloader, source_updates_from_info
from underfind.backend.pipeline.media import extract_audio, extract_frame, has_audio_stream, probe_duration
from underfind.backend.pipeline.ocr import OnScreenTextDetector
from underfind.backend.pipeline.phash import dhash
from underfind.backend.pipeline.transcribe import WhisperTranscriber
from underfind.backend.schemas.pipeline import Job, Transcript


@dataclass
class Workspace:
    """Artifact locations. Source files are shared by every job (page) localizing the same video."""

    sources_dir: Path = SOURCES_DIR
    jobs_dir: Path = JOBS_DIR

    def source_dir(self, source_key: str) -> Path:
        return self.sources_dir / source_key.replace(":", "_")

    def job_dir(self, job_id: str) -> Path:
        return self.jobs_dir / job_id


@dataclass
class StageContext:
    repo: PipelineRepository
    workspace: Workspace = field(default_factory=Workspace)
    downloader: YtDlpDownloader = field(default_factory=YtDlpDownloader)
    transcriber: WhisperTranscriber = field(default_factory=WhisperTranscriber)
    ocr: Optional[OnScreenTextDetector] = field(default_factory=OnScreenTextDetector)


def _require_source(job: Job) -> None:
    if job.source is None:
        raise PermanentStageError(f"Job {job.id} has no source video record.")


def download_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """
    found -> downloaded: fetch the video once per source, refresh metadata, hash a reference frame,
    and stop if it's a reupload of a source another active job already uses.
    """
    _require_source(job)
    src_dir = ctx.workspace.source_dir(job.source_key)
    video_path = src_dir / "source.mp4"

    if video_path.exists():
        logger.debug("Source %s already downloaded; reusing %s", job.source_key, video_path)
    else:
        result = ctx.downloader.download(job.source.url, src_dir)
        updates = source_updates_from_info(result.info)
        ctx.repo.upsert_source(job.source.model_copy(update=updates))

    duration = probe_duration(video_path)

    if not duration:
        raise PermanentStageError(f"Downloaded file for {job.source_key} has no readable duration (corrupt or not a video).")

    frame_path = extract_frame(video_path, min(PHASH_FRAME_SECONDS, duration / 2), src_dir / "frame.jpg")

    with Image.open(frame_path) as frame:
        phash = dhash(frame)

    ctx.repo.set_source_phash(job.source_key, phash)

    for similar, distance in ctx.repo.find_similar_sources(phash, exclude_key=job.source_key):
        other_job = ctx.repo.get_active_source_job_id(similar.key)

        if other_job and other_job != job.id:
            raise DuplicateSourceError(job.source_key, similar.key, other_job, distance)

    ctx.repo.set_artifact(job.id, "source_video", str(video_path))
    ctx.repo.set_artifact(job.id, "frame", str(frame_path))


def transcribe_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """downloaded -> transcribed: speech to timestamped text + language, and flag burned-in on-screen text."""
    _require_source(job)
    src_dir = ctx.workspace.source_dir(job.source_key)
    video_path = src_dir / "source.mp4"
    transcript_path = src_dir / "transcript.json"

    if not video_path.exists():
        raise PermanentStageError(f"Source video missing at {video_path}; move the job back to 'found' to re-download.")

    if transcript_path.exists():
        transcript = Transcript.model_validate_json(transcript_path.read_text(encoding="utf-8"))
        logger.debug("Source %s already transcribed; reusing %s", job.source_key, transcript_path)
    else:
        duration = probe_duration(video_path) or 0.0

        if has_audio_stream(video_path):
            audio_path = extract_audio(video_path, src_dir / "audio.wav")
            transcript = ctx.transcriber.transcribe(audio_path)
        else:
            logger.info("Source %s has no audio stream; storing an empty transcript", job.source_key)
            transcript = Transcript()

        transcript.duration_seconds = round(duration, 3)

        if ctx.ocr is not None:
            transcript.onscreen_text = ctx.ocr.detect(video_path, duration)

        transcript_path.write_text(json.dumps(transcript.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    updates = {"language": transcript.language}

    if transcript.onscreen_text is not None:
        updates["has_onscreen_text"] = bool(transcript.onscreen_text)

    ctx.repo.upsert_source(job.source.model_copy(update={k: v for k, v in updates.items() if v is not None}))
    ctx.repo.set_artifact(job.id, "transcript", str(transcript_path))
