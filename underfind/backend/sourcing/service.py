from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from underfind.backend.core.errors import NotFoundError, SourceAlreadyUsedError
from underfind.backend.core.logger import logger
from underfind.backend.core.niches import Niche, list_niches, load_niche
from underfind.backend.core.utils import parse_source_url
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.db.sourcing_repo import SourcingRepository
from underfind.backend.schemas.pipeline import Platform, SourceVideo
from underfind.backend.schemas.sourcing import (
    Candidate,
    CandidateStatus,
    IngestCandidateRequest,
    ScanReport,
)
from underfind.backend.services.job_service import JobService
from underfind.backend.sourcing.scanners import Scanner, build_scanners
from underfind.backend.sourcing.scoring import score_candidate

ScannerFactory = Callable[[Niche, Any, int], List[Scanner]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourcingService:
    """
    Finds posts worth modeling for a niche: runs the niche's scanners, scores every post, keeps the scored
    candidates (skipping sources already used), and optionally turns the best into jobs for the niche's pages.
    """

    def __init__(
        self,
        pipeline: PipelineRepository,
        sourcing: SourcingRepository,
        youtube: Any = None,
        scanner_factory: ScannerFactory = build_scanners,
        clock: Callable[[], datetime] = _now,
    ):
        self.pipeline = pipeline
        self.sourcing = sourcing
        self.youtube = youtube
        self.scanner_factory = scanner_factory
        self.clock = clock
        self._scan_lock = threading.Lock()

    def _niche(self, name: str) -> Niche:
        try:
            niche = load_niche(name)
        except KeyError as err:
            raise NotFoundError(str(err.args[0])) from err

        if niche is None:
            raise NotFoundError("A niche name is required.")

        return niche

    def _classify(
        self,
        source: SourceVideo,
        niche: Niche,
        scanner: str,
        seed: bool,
    ) -> Candidate:
        score, scores, reason = score_candidate(source, niche, now=self.clock(), seed=seed)
        used_by = self.pipeline.get_source_job_id(source.key)

        if used_by:
            status, reason = CandidateStatus.SKIPPED, f"auto: already used by job {used_by}"
        elif reason:
            status = CandidateStatus.REJECTED
        else:
            status = CandidateStatus.NEW

        return Candidate(
            source_key=source.key, niche=niche.name, scanner=scanner, score=score, scores=scores,
            status=status, reason=reason, source=source,
        )

    def _store(self, candidate: Candidate) -> Candidate:
        self.pipeline.upsert_source(candidate.source)
        return self.sourcing.save_candidate(candidate)

    def scan(self, niche_name: str, dry_run: bool = False) -> ScanReport:
        """One pass over every scanner of the niche. A failing scanner is reported; the others still count."""
        niche = self._niche(niche_name)

        with self._scan_lock:
            report = ScanReport(niche=niche.name, started_at=self.clock().isoformat(), dry_run=dry_run)
            scanners = self.scanner_factory(niche, self.youtube, self.sourcing.count_scans(niche.name))
            collected: Dict[str, Tuple[SourceVideo, Scanner]] = {}

            for scanner in scanners:
                try:
                    items = scanner.scan(niche)
                except Exception as err:
                    logger.warning("Scanner %s failed for niche %s: %s", scanner.name, niche.name, err)
                    report.errors[scanner.name] = f"{type(err).__name__}: {err}"[:300]
                    continue

                for source in items:
                    collected.setdefault(source.key, (source, scanner))

            report.found = len(collected)
            fresh: List[Candidate] = []

            for source, scanner in collected.values():
                candidate = self._classify(source, niche, scanner.name, scanner.seed)

                if not dry_run:
                    candidate = self._store(candidate)

                if candidate.status == CandidateStatus.NEW:
                    report.new += 1
                    fresh.append(candidate)
                elif candidate.status == CandidateStatus.REJECTED:
                    report.rejected += 1
                elif candidate.status == CandidateStatus.SKIPPED:
                    report.skipped += 1

            if not dry_run and niche.auto_queue.enabled:
                report.queued = self._auto_queue(niche)

            report.top = sorted(fresh, key=lambda c: c.score, reverse=True)[:10]
            report.finished_at = self.clock().isoformat()
            stored = self.sourcing.record_scan(report)

        logger.info(
            "Scan %s: %d found, %d new, %d rejected, %d skipped, %d queued, %d scanner errors",
            niche.name, report.found, report.new, report.rejected, report.skipped, report.queued, len(report.errors),
        )
        return stored.model_copy(update={"top": report.top})

    def _auto_queue(self, niche: Niche) -> int:
        queued = 0

        for candidate in self.sourcing.list_candidates(niche.name, CandidateStatus.NEW, limit=niche.auto_queue.max_per_scan):
            try:
                self.queue(candidate.id, mode=niche.auto_queue.mode)
                queued += 1
            except (SourceAlreadyUsedError, ValueError) as err:
                logger.info("Auto-queue skipped candidate %s: %s", candidate.id, err)

        return queued

    def pages_for(self, niche: str) -> List[int]:
        return [p.id for p in self.pipeline.list_pages(active_only=True) if p.niche == niche]

    def queue(
        self,
        candidate_id: int,
        page_ids: Optional[List[int]] = None,
        mode: str = "subtitles",
        local_only: Optional[bool] = None,
    ) -> Candidate:
        """Opens one job per target page (default: every active page of the niche)."""
        candidate = self.sourcing.get_candidate(candidate_id)
        targets = page_ids or self.pages_for(candidate.niche)

        if not targets:
            raise ValueError(f"No active page uses niche '{candidate.niche}'; pass page_ids or set a page's niche.")

        service = JobService(self.pipeline)
        job_ids: List[str] = []

        try:
            for i, page_id in enumerate(targets):
                # The first job registers the source; the other pages of this same decision reuse it.
                job = service.open_job(candidate.source, page_id=page_id, mode=mode, force=i > 0, local_only=local_only)
                job_ids.append(job.id)
        except SourceAlreadyUsedError as err:
            if not job_ids:
                self.sourcing.set_status(candidate_id, CandidateStatus.SKIPPED, f"auto: already used by job {err.existing_job_id}")
                raise

        return self.sourcing.set_status(candidate_id, CandidateStatus.QUEUED, None, candidate.job_ids + job_ids)

    def reject(self, candidate_id: int, reason: Optional[str] = None) -> Candidate:
        return self.sourcing.set_status(candidate_id, CandidateStatus.REJECTED, reason or "rejected by hand")

    def ingest(self, req: IngestCandidateRequest) -> Candidate:
        """A candidate found outside underfind (vidIQ via a Claude routine, n8n, a browser bookmarklet)."""
        niche = self._niche(req.niche)
        platform, source_id = parse_source_url(req.url)
        source = SourceVideo(
            platform=Platform(platform), source_id=source_id, url=req.url, title=req.title, caption=req.caption,
            author_handle=req.author_handle, views=req.views, likes=req.likes, comments_count=req.comments_count,
            followers=req.followers, duration_seconds=req.duration_seconds, published_at=req.published_at,
        )
        # Picked on purpose by a person or tool that searched the niche: relevance is taken as given.
        candidate = self._store(self._classify(source, niche, req.scanner, seed=True))

        if niche.auto_queue.enabled and candidate.status == CandidateStatus.NEW:
            self._auto_queue(niche)
            candidate = self.sourcing.get_candidate(candidate.id)

        return candidate

    def run_due_scans(self) -> List[ScanReport]:
        """Called by the worker on every poll: scans each niche whose scan.every_minutes has elapsed."""
        if os.environ.get("SOURCING_ENABLED", "true").lower() in ("0", "false", "no"):
            return []

        reports: List[ScanReport] = []
        now = self.clock()

        for name in list_niches():
            try:
                niche = load_niche(name)
            except Exception as err:
                logger.error("Niche %s has an invalid config: %s", name, err)
                continue

            if niche.scan.every_minutes <= 0:
                continue

            last = self.sourcing.last_scan_at(name)

            if last is not None and now - last < timedelta(minutes=niche.scan.every_minutes):
                continue

            try:
                reports.append(self.scan(name))
            except Exception as err:
                logger.error("Scheduled scan of %s failed: %s", name, err)

        return reports


_default: Optional[SourcingService] = None
_default_lock = threading.Lock()


def get_sourcing_service() -> SourcingService:
    global _default

    with _default_lock:
        if _default is None:
            from underfind.backend.db.pipeline_repo import pipeline_repo
            from underfind.backend.services.youtube_service import YouTubeService

            youtube = YouTubeService()
            _default = SourcingService(
                pipeline_repo,
                SourcingRepository(pipeline_repo.db_path, pipeline_repo),
                youtube=youtube if youtube.api_key else None,
            )

        return _default
