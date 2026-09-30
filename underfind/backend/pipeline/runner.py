from __future__ import annotations

import os
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, Tuple

from underfind.backend.core.constants import (
    STAGE_MAX_ATTEMPTS,
    STAGE_BACKOFF_BASE_SECONDS,
    WORKER_POLL_INTERVAL_SECONDS,
    WORKER_MAX_PARALLEL_JOBS,
)
from underfind.backend.core.errors import DuplicateSourceError, PermanentStageError
from underfind.backend.core.logger import logger
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.pipeline.stages import (
    StageContext,
    download_stage,
    transcribe_stage,
    translate_stage,
    voice_stage,
    render_stage,
)
from underfind.backend.schemas.pipeline import Job, JobStatus

StageHandler = Callable[[Job, StageContext], None]
ReadyCheck = Callable[[Job], bool]


def _always_ready(job: Job) -> bool:
    return True


def _has_page(job: Job) -> bool:
    return job.page_id is not None


def _translation_approved(job: Job) -> bool:
    return job.translation_approved


# current status -> (status after success, handler, gate). A job whose gate is closed waits (review, page assignment);
# statuses without a handler (later phases) stop the run. Keep gates in sync with PipelineRepository.list_runnable_job_ids.
STAGE_HANDLERS: Dict[JobStatus, Tuple[JobStatus, StageHandler, ReadyCheck]] = {
    JobStatus.FOUND: (JobStatus.DOWNLOADED, download_stage, _always_ready),
    JobStatus.DOWNLOADED: (JobStatus.TRANSCRIBED, transcribe_stage, _always_ready),
    JobStatus.TRANSCRIBED: (JobStatus.TRANSLATED, translate_stage, _has_page),
    JobStatus.TRANSLATED: (JobStatus.VOICED, voice_stage, _translation_approved),
    JobStatus.VOICED: (JobStatus.RENDERED, render_stage, _always_ready),
}


class PipelineRunner:
    """
    Advances jobs through automated stages.
    Each run claims the job (so parallel workers never process it twice), retries transient errors with
    exponential backoff, fails immediately on permanent errors, and discards post-download duplicates.
    """

    def __init__(
        self,
        ctx: StageContext,
        handlers: Optional[Dict[JobStatus, Tuple[JobStatus, StageHandler, ReadyCheck]]] = None,
        max_attempts: int = STAGE_MAX_ATTEMPTS,
        backoff_base: float = STAGE_BACKOFF_BASE_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        worker_id: Optional[str] = None,
    ):
        self.ctx = ctx
        self.repo: PipelineRepository = ctx.repo
        self.handlers = handlers if handlers is not None else STAGE_HANDLERS
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self._sleep = sleep
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"

    def run_next(
        self,
        job_id: str,
    ) -> Job:
        """Runs the handler for the job's current status once (with retries). Returns the job afterwards."""
        job = self.repo.get_job(job_id)

        if job.status not in self.handlers:
            return job

        target, handler, ready = self.handlers[job.status]

        if not ready(job):
            logger.debug("Job %s is waiting at '%s' (%s closed)", job_id, job.status.value, ready.__name__)
            return job

        if not self.repo.claim_job(job_id, self.worker_id):
            logger.debug("Job %s is locked by another worker; skipping", job_id)
            return job

        try:
            self._run_with_retries(job_id, target, handler)
        finally:
            self.repo.release_job(job_id, self.worker_id)

        return self.repo.get_job(job_id)

    def _run_with_retries(
        self,
        job_id: str,
        target: JobStatus,
        handler: StageHandler,
    ) -> None:
        for attempt in range(1, self.max_attempts + 1):
            self.repo.record_attempt(job_id)
            job = self.repo.get_job(job_id)

            try:
                handler(job, self.ctx)
                self.repo.transition(job_id, target, note=f"auto: {handler.__name__}")
                return

            except DuplicateSourceError as err:
                logger.info("Job %s discarded: %s", job_id, err)
                self.repo.transition(job_id, JobStatus.DISCARDED, note=str(err))
                return

            except PermanentStageError as err:
                logger.warning("Job %s failed permanently in %s: %s", job_id, handler.__name__, err)
                self.repo.transition(job_id, JobStatus.FAILED, error=str(err))
                return

            except Exception as err:
                if attempt == self.max_attempts:
                    logger.error("Job %s failed in %s after %d attempts: %s", job_id, handler.__name__, attempt, err)
                    self.repo.transition(job_id, JobStatus.FAILED, error=f"{type(err).__name__}: {err}")
                    return

                delay = self.backoff_base * (2 ** (attempt - 1))
                logger.warning("Job %s %s attempt %d/%d failed (%s); retrying in %.0fs", job_id, handler.__name__, attempt, self.max_attempts, err, delay)
                self._sleep(delay)

    def run_until_blocked(
        self,
        job_id: str,
    ) -> Job:
        """Advances a job stage after stage until it reaches a status without a handler, fails, or is locked elsewhere."""
        while True:
            before = self.repo.get_job(job_id)
            after = self.run_next(job_id)

            if after.status == before.status or after.status not in self.handlers:
                return after

    def tick(
        self,
        limit: int = 20,
        max_parallel: Optional[int] = None,
    ) -> List[Job]:
        """One polling pass: picks runnable jobs and advances each as far as possible."""
        job_ids = self.repo.list_runnable_job_ids(list(self.handlers.keys()), limit=limit)

        if not job_ids:
            return []

        workers = max_parallel or int(os.environ.get("WORKER_MAX_PARALLEL_JOBS", WORKER_MAX_PARALLEL_JOBS))
        logger.info("Pipeline tick: %d runnable jobs (%d parallel)", len(job_ids), workers)

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pipeline") as pool:
            return list(pool.map(self.run_until_blocked, job_ids))

    def run_forever(
        self,
        stop_event: threading.Event,
        interval: Optional[float] = None,
    ) -> None:
        poll = interval or float(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", WORKER_POLL_INTERVAL_SECONDS))
        logger.info("Pipeline worker %s started (poll every %.0fs)", self.worker_id, poll)

        while not stop_event.is_set():
            try:
                self.tick()
            except Exception as err:
                logger.error("Pipeline tick crashed: %s", err)

            stop_event.wait(poll)

        logger.info("Pipeline worker %s stopped", self.worker_id)


_default_runner: Optional[PipelineRunner] = None
_default_runner_lock = threading.Lock()


def get_default_runner() -> PipelineRunner:
    """Process-wide runner so the Whisper model loads once."""
    global _default_runner

    with _default_runner_lock:
        if _default_runner is None:
            from underfind.backend.db.pipeline_repo import pipeline_repo
            _default_runner = PipelineRunner(StageContext(repo=pipeline_repo))

        return _default_runner
