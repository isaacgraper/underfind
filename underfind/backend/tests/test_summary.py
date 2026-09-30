from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.db.sourcing_repo import SourcingRepository
from underfind.backend.dependencies import get_pipeline_repo, get_sourcing_service
from underfind.backend.main import app
from underfind.backend.schemas.pipeline import JobStatus, SourceVideo, Platform
from underfind.backend.services.job_service import JobService
from underfind.backend.sourcing.service import SourcingService


def _job(repo: PipelineRepository, n: int, status: JobStatus, **approvals):
    job = JobService(repo).open_job(SourceVideo(platform=Platform.INSTAGRAM, source_id=f"S{n}", url=f"https://www.instagram.com/reel/S{n}/"))

    with repo._get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, translation_approved = ?, render_approved = ? WHERE id = ?",
            (status.value, int(approvals.get("translation", False)), int(approvals.get("render", False)), job.id),
        )
        conn.commit()

    return job


def test_lane_counts_and_summary_endpoint(tmp_path: Path):
    repo = PipelineRepository(db_path=tmp_path / "db.sqlite3")
    _job(repo, 1, JobStatus.FOUND)
    _job(repo, 2, JobStatus.TRANSCRIBED)
    _job(repo, 3, JobStatus.TRANSLATED)                       # waits for translation approval
    _job(repo, 4, JobStatus.TRANSLATED, translation=True)     # approved, worker will voice it
    _job(repo, 5, JobStatus.RENDERED)                         # waits for render approval
    _job(repo, 6, JobStatus.RENDERED, render=True)
    _job(repo, 7, JobStatus.FAILED)
    _job(repo, 8, JobStatus.EXPORTED)
    _job(repo, 9, JobStatus.DISCARDED)

    assert repo.lane_counts() == {"needs_you": 2, "working": 4, "failed": 1, "done": 1}

    sourcing = SourcingService(repo, SourcingRepository(repo.db_path, repo), scanner_factory=lambda *a: [])
    app.dependency_overrides[get_pipeline_repo] = lambda: repo
    app.dependency_overrides[get_sourcing_service] = lambda: sourcing

    try:
        body = TestClient(app).get("/api/summary").json()
    finally:
        app.dependency_overrides.clear()

    assert body == {"ai_mode": "local", "worker_running": False, "inbox_new": 0, "needs_you": 2, "working": 4, "failed": 1, "done": 1}
