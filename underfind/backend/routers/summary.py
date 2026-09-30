from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo, get_sourcing_service
from underfind.backend.pipeline.stages import current_ai_mode
from underfind.backend.schemas.sourcing import CandidateStatus

router = APIRouter(tags=["Dashboard & Health"])


class Summary(BaseModel):
    ai_mode: str
    worker_running: bool
    inbox_new: int
    needs_you: int
    working: int
    failed: int
    done: int


@router.get("/summary", response_model=Summary)
def get_summary(
    request: Request,
    repo: PipelineRepository = Depends(get_pipeline_repo),
    sourcing: Optional[object] = Depends(get_sourcing_service),
) -> Summary:
    """Everything the top bar shows: AI mode, worker state, inbox count and the pipeline lane counts."""
    lanes = repo.lane_counts()
    inbox_new = len(sourcing.sourcing.list_candidates(None, CandidateStatus.NEW, limit=1000))
    return Summary(
        ai_mode=current_ai_mode(),
        worker_running=bool(getattr(request.app.state, "worker_running", False)),
        inbox_new=inbox_new,
        **lanes,
    )
