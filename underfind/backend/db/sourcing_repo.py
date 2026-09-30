from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from underfind.backend.core.constants import DATABASE_PATH
from underfind.backend.core.errors import NotFoundError
from underfind.backend.db.migrations import apply_migrations
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.schemas.sourcing import Candidate, CandidateStatus, ScanReport


# Decisions a rescan must not undo: queued, or rejected by hand (automatic rejections carry an "auto:" reason).
_KEPT_DECISION = (
    "candidates.status = 'queued' OR "
    "(candidates.status = 'rejected' AND COALESCE(candidates.reason, '') NOT LIKE 'auto:%')"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourcingRepository:
    """Candidates and scan log, in the same SQLite file as the pipeline (sources are shared)."""

    def __init__(
        self,
        db_path: Path = DATABASE_PATH,
        pipeline: Optional[PipelineRepository] = None,
    ):
        self.db_path = db_path
        self.pipeline = pipeline or PipelineRepository(db_path)

        with self._get_connection() as conn:
            apply_migrations(conn)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _row_to_candidate(self, row: sqlite3.Row, with_source: bool = True) -> Candidate:
        return Candidate(
            id=row["id"],
            source_key=row["source_key"],
            niche=row["niche"],
            scanner=row["scanner"],
            score=row["score"],
            scores=json.loads(row["scores_json"]) if row["scores_json"] else {},
            status=CandidateStatus(row["status"]),
            reason=row["reason"],
            job_ids=json.loads(row["job_ids_json"]) if row["job_ids_json"] else [],
            discovered_at=row["discovered_at"],
            updated_at=row["updated_at"],
            source=self.pipeline.get_source(row["source_key"]) if with_source else None,
        )

    def get_candidate_by_key(self, source_key: str, niche: str) -> Optional[Candidate]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE source_key = ? AND niche = ?", (source_key, niche)).fetchone()

        return self._row_to_candidate(row) if row else None

    def get_candidate(self, candidate_id: int) -> Candidate:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()

        if not row:
            raise NotFoundError(f"Candidate {candidate_id} not found.")

        return self._row_to_candidate(row)

    def save_candidate(self, candidate: Candidate) -> Candidate:
        """
        Inserts or refreshes a candidate (same source + niche). Metrics and score refresh on every scan; a decision
        already taken (queued/rejected by hand) is kept.
        """
        now = _now()

        with self._get_connection() as conn:
            conn.execute(
                f"""
                INSERT INTO candidates (source_key, niche, scanner, score, scores_json, status, reason, job_ids_json, discovered_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key, niche) DO UPDATE SET
                    score = excluded.score,
                    scores_json = excluded.scores_json,
                    status = CASE WHEN {_KEPT_DECISION} THEN candidates.status ELSE excluded.status END,
                    reason = CASE WHEN {_KEPT_DECISION} THEN candidates.reason ELSE excluded.reason END,
                    updated_at = excluded.updated_at
                """,
                (
                    candidate.source_key, candidate.niche, candidate.scanner, candidate.score,
                    json.dumps(candidate.scores), candidate.status.value, candidate.reason,
                    json.dumps(candidate.job_ids), now, now,
                ),
            )
            conn.commit()

        return self.get_candidate_by_key(candidate.source_key, candidate.niche)

    def set_status(
        self,
        candidate_id: int,
        status: CandidateStatus,
        reason: Optional[str] = None,
        job_ids: Optional[List[str]] = None,
    ) -> Candidate:
        current = self.get_candidate(candidate_id)
        ids = job_ids if job_ids is not None else current.job_ids

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE candidates SET status = ?, reason = ?, job_ids_json = ?, updated_at = ? WHERE id = ?",
                (status.value, reason, json.dumps(ids), _now(), candidate_id),
            )
            conn.commit()

        return self.get_candidate(candidate_id)

    def list_candidates(
        self,
        niche: Optional[str] = None,
        status: Optional[CandidateStatus] = None,
        limit: int = 100,
    ) -> List[Candidate]:
        clauses, params = [], []

        if niche:
            clauses.append("niche = ?")
            params.append(niche)

        if status:
            clauses.append("status = ?")
            params.append(status.value)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM candidates {where} ORDER BY score DESC, discovered_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()

        return [self._row_to_candidate(r) for r in rows]

    def record_scan(self, report: ScanReport) -> ScanReport:
        payload = json.dumps(report.model_dump(exclude={"id", "top"}))

        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO scans (niche, started_at, finished_at, report_json) VALUES (?, ?, ?, ?)",
                (report.niche, report.started_at, report.finished_at, payload),
            )
            conn.commit()

        return report.model_copy(update={"id": cursor.lastrowid})

    def last_scan_at(self, niche: str) -> Optional[datetime]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT started_at, report_json FROM scans WHERE niche = ? ORDER BY started_at DESC", (niche,)
            ).fetchall()

        for r in row:
            if not json.loads(r["report_json"] or "{}").get("dry_run"):
                return datetime.fromisoformat(r["started_at"])

        return None

    def count_scans(self, niche: str) -> int:
        with self._get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM scans WHERE niche = ?", (niche,)).fetchone()[0]

    def list_scans(self, niche: Optional[str] = None, limit: int = 20) -> List[ScanReport]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM scans WHERE (? IS NULL OR niche = ?) ORDER BY started_at DESC LIMIT ?",
                (niche, niche, limit),
            ).fetchall()

        return [ScanReport(id=r["id"], **json.loads(r["report_json"] or "{}")) for r in rows]
