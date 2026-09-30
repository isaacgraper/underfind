from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from underfind.backend.dependencies import get_sourcing_service
from underfind.backend.schemas.sourcing import (
    Candidate,
    CandidateStatus,
    IngestCandidateRequest,
    QueueCandidateRequest,
    RejectCandidateRequest,
    ScanReport,
)

router = APIRouter(tags=["Sourcing"])


@router.post("/scan/{niche}", response_model=ScanReport)
def scan_niche(
    niche: str,
    dry_run: bool = Query(False, description="Score and report without saving candidates or queueing jobs"),
    service=Depends(get_sourcing_service),
) -> ScanReport:
    """Runs every scanner of the niche now (seed pages, keyword search), scores what they find and stores candidates."""
    return service.scan(niche, dry_run=dry_run)


@router.get("/scans", response_model=List[ScanReport])
def list_scans(
    niche: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    service=Depends(get_sourcing_service),
) -> List[ScanReport]:
    return service.sourcing.list_scans(niche, limit)


@router.get("/candidates", response_model=List[Candidate])
def list_candidates(
    niche: Optional[str] = Query(None),
    status: Optional[CandidateStatus] = Query(CandidateStatus.NEW),
    limit: int = Query(100, ge=1, le=1000),
    service=Depends(get_sourcing_service),
) -> List[Candidate]:
    """Scored candidates, best first (default: new ones waiting for a decision)."""
    return service.sourcing.list_candidates(niche, status, limit)


@router.post("/candidates", response_model=Candidate)
def ingest_candidate(
    req: IngestCandidateRequest,
    service=Depends(get_sourcing_service),
) -> Candidate:
    """Adds a post found elsewhere (vidIQ in a Claude routine, n8n, ...); scored like scanned posts."""
    return service.ingest(req)


@router.post("/candidates/{candidate_id}/queue", response_model=Candidate)
def queue_candidate(
    candidate_id: int,
    req: Optional[QueueCandidateRequest] = None,
    service=Depends(get_sourcing_service),
) -> Candidate:
    """Turns a candidate into jobs: one per target page (default: every active page of its niche)."""
    req = req or QueueCandidateRequest()
    return service.queue(candidate_id, page_ids=req.page_ids, mode=req.mode, local_only=req.local_only)


@router.post("/candidates/{candidate_id}/reject", response_model=Candidate)
def reject_candidate(
    candidate_id: int,
    req: Optional[RejectCandidateRequest] = None,
    service=Depends(get_sourcing_service),
) -> Candidate:
    return service.reject(candidate_id, (req or RejectCandidateRequest()).reason)
