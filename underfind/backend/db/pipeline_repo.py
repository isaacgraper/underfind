from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from underfind.backend.core.constants import (
    DATABASE_PATH,
    DEFAULT_LOCALIZATION_MODE,
    JOB_LOCK_STALE_MINUTES,
    PHASH_MAX_DISTANCE,
)
from underfind.backend.core.errors import InvalidTransitionError, NotFoundError
from underfind.backend.core.logger import logger
from underfind.backend.core.utils import hamming_distance_hex
from underfind.backend.db.migrations import apply_migrations
from underfind.backend.schemas.pipeline import (
    Job,
    MediaType,
    JobEvent,
    JobStatus,
    PageProfile,
    Platform,
    RenderTemplate,
    SourceVideo,
    PIPELINE_STAGES,
    PAGE_REQUIRED_FROM,
)

_SOURCE_FIELDS = [
    "platform", "source_id", "url", "title", "caption", "author_handle", "author_name",
    "thumbnail_url", "views", "likes", "comments_count", "followers", "duration_seconds",
    "published_at", "language", "phash", "has_onscreen_text",
]
# Column list for source_videos: scalar model fields plus the JSON/enum media columns.
_SOURCE_COLUMNS = [*_SOURCE_FIELDS, "media_type", "media_json"]


def _source_row_values(source: SourceVideo) -> Dict[str, Any]:
    values = source.model_dump()
    values["platform"] = source.platform.value
    values["media_type"] = source.media_type.value if source.media_type else None
    # Empty list means "unknown yet": stored as NULL so an upsert never erases known files.
    values["media_json"] = json.dumps(source.media_files) if source.media_files else None
    return values


def _source_from_values(get) -> SourceVideo:
    data = {field: get(field) for field in _SOURCE_FIELDS}
    data["platform"] = Platform(data["platform"])
    media_type = get("media_type")
    media_json = get("media_json")
    return SourceVideo(
        **data,
        media_type=MediaType(media_type) if media_type else None,
        media_files=json.loads(media_json) if media_json else [],
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_transition(
    current: JobStatus,
    target: JobStatus,
    failed_from: Optional[JobStatus] = None,
    has_page: bool = False,
) -> None:
    """
    Validates a job status change:
    - forward moves advance exactly one stage; backward moves (re-run) may jump to any earlier stage
    - any active job can fail or be discarded; exported jobs are final except for re-runs
    - failed jobs retry from the stage that failed or earlier; discarded jobs can only be restored to 'found'
    - page-specific stages (translated onward) need a target page
    """
    if current == target:
        raise InvalidTransitionError(f"Job is already '{current.value}'.")

    if target == JobStatus.FAILED:
        if current in (JobStatus.EXPORTED, JobStatus.DISCARDED):
            raise InvalidTransitionError(f"A '{current.value}' job cannot fail.")
        return

    if target == JobStatus.DISCARDED:
        if current == JobStatus.EXPORTED:
            raise InvalidTransitionError("An exported job cannot be discarded.")
        return

    if current == JobStatus.DISCARDED:
        if target != JobStatus.FOUND:
            raise InvalidTransitionError("A discarded job can only be restored to 'found'.")
        return

    target_idx = PIPELINE_STAGES.index(target)

    if target_idx >= PIPELINE_STAGES.index(PAGE_REQUIRED_FROM) and not has_page:
        raise InvalidTransitionError(f"Assign a target page before moving a job to '{target.value}'.")

    if current == JobStatus.FAILED:
        ceiling = PIPELINE_STAGES.index(failed_from) if failed_from else 0

        if target_idx > ceiling:
            raise InvalidTransitionError(
                f"A failed job can only be retried from '{(failed_from or JobStatus.FOUND).value}' or an earlier stage."
            )
        return

    current_idx = PIPELINE_STAGES.index(current)

    if target_idx > current_idx + 1:
        raise InvalidTransitionError(
            f"Cannot skip stages: '{current.value}' can only advance to '{PIPELINE_STAGES[current_idx + 1].value}'."
        )


class PipelineRepository:
    """SQLite persistence for source videos, localization jobs, page profiles and render templates."""

    def __init__(
        self,
        db_path: Path = DATABASE_PATH,
    ):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            apply_migrations(conn)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ------------------------------------------------------------------ sources

    @staticmethod
    def _row_to_source(row: sqlite3.Row) -> SourceVideo:
        return _source_from_values(lambda column: row[column])

    def upsert_source(
        self,
        source: SourceVideo,
    ) -> SourceVideo:
        """Inserts a source video or refreshes its metadata, never overwriting known values with nulls."""
        now = _now()
        values = _source_row_values(source)
        update_cols = [c for c in _SOURCE_COLUMNS if c not in ("platform", "source_id")]

        with self._get_connection() as conn:
            conn.execute(
                f"""
                INSERT INTO source_videos (source_key, {", ".join(_SOURCE_COLUMNS)}, created_at, updated_at)
                VALUES (?, {", ".join("?" for _ in _SOURCE_COLUMNS)}, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    {", ".join(f"{c} = COALESCE(excluded.{c}, {c})" for c in update_cols)},
                    updated_at = excluded.updated_at
                """,
                (source.key, *[values[c] for c in _SOURCE_COLUMNS], now, now)
            )
            conn.commit()

        logger.trace("Upserted source video %s", source.key)
        return self.get_source(source.key)

    def get_source(
        self,
        source_key: str,
    ) -> Optional[SourceVideo]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM source_videos WHERE source_key = ?", (source_key,)).fetchone()

        return self._row_to_source(row) if row else None

    def set_source_phash(
        self,
        source_key: str,
        phash: str,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE source_videos SET phash = ?, updated_at = ? WHERE source_key = ?",
                (phash, _now(), source_key)
            )
            conn.commit()

    def find_similar_sources(
        self,
        phash: str,
        max_distance: int = PHASH_MAX_DISTANCE,
        exclude_key: Optional[str] = None,
    ) -> List[tuple[SourceVideo, int]]:
        """Known sources whose perceptual hash is within max_distance bits, closest first (cross-platform reuploads)."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM source_videos WHERE phash IS NOT NULL").fetchall()

        matches: List[tuple[SourceVideo, int]] = []

        for row in rows:
            if row["source_key"] == exclude_key or len(row["phash"]) != len(phash):
                continue

            distance = hamming_distance_hex(phash, row["phash"])

            if distance <= max_distance:
                matches.append((self._row_to_source(row), distance))

        return sorted(matches, key=lambda m: m[1])

    def find_similar_source(
        self,
        phash: str,
        max_distance: int = PHASH_MAX_DISTANCE,
        exclude_key: Optional[str] = None,
    ) -> Optional[SourceVideo]:
        matches = self.find_similar_sources(phash, max_distance, exclude_key)
        return matches[0][0] if matches else None

    def get_source_job_id(
        self,
        source_key: str,
    ) -> Optional[str]:
        """Returns the first job created for a source; any job (including discarded) marks the source as used."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE source_key = ? ORDER BY created_at LIMIT 1",
                (source_key,)
            ).fetchone()

        return row["id"] if row else None

    def get_active_source_job_id(
        self,
        source_key: str,
    ) -> Optional[str]:
        """Returns the first non-discarded job of a source."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE source_key = ? AND status != ? ORDER BY created_at LIMIT 1",
                (source_key, JobStatus.DISCARDED.value)
            ).fetchone()

        return row["id"] if row else None

    def is_source_used(
        self,
        platform: str,
        source_id: str,
    ) -> bool:
        return self.get_source_job_id(f"{platform}:{source_id}") is not None

    # --------------------------------------------------------------------- jobs

    def _row_to_job(
        self,
        row: sqlite3.Row,
        source: Optional[SourceVideo] = None,
    ) -> Job:
        return Job(
            id=row["id"],
            source_key=row["source_key"],
            page_id=row["page_id"],
            status=JobStatus(row["status"]),
            failed_from=JobStatus(row["failed_from"]) if row["failed_from"] else None,
            error=row["error"],
            mode=row["mode"],
            artifacts=json.loads(row["artifacts_json"]) if row["artifacts_json"] else {},
            notes=row["notes"],
            attempts=row["attempts"] or 0,
            locked_by=row["locked_by"],
            translation_approved=bool(row["translation_approved"]),
            render_approved=bool(row["render_approved"]),
            local_only=None if row["local_only"] is None else bool(row["local_only"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            source=source,
        )

    def create_job(
        self,
        source_key: str,
        page_id: Optional[int] = None,
        mode: str = DEFAULT_LOCALIZATION_MODE,
        note: Optional[str] = None,
        local_only: Optional[bool] = None,
    ) -> Job:
        if not self.get_source(source_key):
            raise NotFoundError(f"Source video '{source_key}' not found.")

        if page_id is not None and not self.get_page(page_id):
            raise NotFoundError(f"Page profile {page_id} not found.")

        job_id = uuid.uuid4().hex[:12]
        now = _now()

        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO jobs (id, source_key, page_id, status, mode, artifacts_json, notes, local_only, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, '{}', ?, ?, ?, ?)
                    """,
                    (job_id, source_key, page_id, JobStatus.FOUND.value, mode, note, None if local_only is None else int(local_only), now, now)
                )
            except sqlite3.IntegrityError as err:
                raise InvalidTransitionError(f"Source '{source_key}' already has a job for page {page_id}.") from err

            conn.execute(
                "INSERT INTO job_events (job_id, from_status, to_status, note, created_at) VALUES (?, NULL, ?, ?, ?)",
                (job_id, JobStatus.FOUND.value, note, now)
            )
            conn.commit()

        logger.info("Created job %s for source %s (page=%s, mode=%s)", job_id, source_key, page_id, mode)
        return self.get_job(job_id)

    def get_job(
        self,
        job_id: str,
    ) -> Job:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

        if not row:
            raise NotFoundError(f"Job '{job_id}' not found.")

        return self._row_to_job(row, self.get_source(row["source_key"]))

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        page_id: Optional[int] = None,
        limit: int = 200,
    ) -> List[Job]:
        clauses: List[str] = []
        params: List[Any] = []

        if status is not None:
            clauses.append("j.status = ?")
            params.append(status.value)

        if page_id is not None:
            clauses.append("j.page_id = ?")
            params.append(page_id)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT j.*, {", ".join(f"s.{c} AS s_{c}" for c in _SOURCE_COLUMNS)}
                FROM jobs j JOIN source_videos s ON s.source_key = j.source_key
                {where}
                ORDER BY j.updated_at DESC
                LIMIT ?
                """,
                (*params, limit)
            ).fetchall()

        jobs: List[Job] = []

        for row in rows:
            jobs.append(self._row_to_job(row, _source_from_values(lambda column, r=row: r[f"s_{column}"])))

        return jobs

    def transition(
        self,
        job_id: str,
        target: JobStatus,
        note: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Job:
        """Moves a job to a new status after validating the state machine, recording the event."""
        job = self.get_job(job_id)
        check_transition(job.status, target, job.failed_from, has_page=job.page_id is not None)

        failed_from = job.status.value if target == JobStatus.FAILED else None
        stored_error = error if target == JobStatus.FAILED else None
        now = _now()

        with self._get_connection() as conn:
            # Attempts are kept on failure (how hard the worker tried) and reset when the job moves on or is retried.
            # Moving back before translation (or before rendering) invalidates that approval.
            stage = PIPELINE_STAGES.index(target) if target in PIPELINE_STAGES else None
            before_translation = stage is not None and stage < PIPELINE_STAGES.index(JobStatus.TRANSLATED)
            before_render = stage is not None and stage < PIPELINE_STAGES.index(JobStatus.RENDERED)
            conn.execute(
                """
                UPDATE jobs SET status = ?, failed_from = ?, error = ?, updated_at = ?,
                    attempts = CASE WHEN ? = 'failed' THEN attempts ELSE 0 END,
                    translation_approved = CASE WHEN ? THEN 0 ELSE translation_approved END,
                    render_approved = CASE WHEN ? THEN 0 ELSE render_approved END
                WHERE id = ?
                """,
                (target.value, failed_from, stored_error, now, target.value, int(before_translation), int(before_render), job_id)
            )
            conn.execute(
                "INSERT INTO job_events (job_id, from_status, to_status, note, created_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, job.status.value, target.value, note or error, now)
            )
            conn.commit()

        logger.debug("Job %s: %s -> %s", job_id, job.status.value, target.value)
        return self.get_job(job_id)

    def claim_job(
        self,
        job_id: str,
        worker_id: str,
        stale_minutes: int = JOB_LOCK_STALE_MINUTES,
    ) -> bool:
        """Atomically locks a job for one worker. Locks older than stale_minutes (crashed worker) can be taken over."""
        now = datetime.now(timezone.utc)
        stale_before = (now - timedelta(minutes=stale_minutes)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs SET locked_by = ?, locked_at = ?
                WHERE id = ? AND (locked_by IS NULL OR locked_by = ? OR locked_at < ?)
                """,
                (worker_id, now.isoformat(), job_id, worker_id, stale_before)
            )
            conn.commit()

        return cursor.rowcount > 0

    def release_job(
        self,
        job_id: str,
        worker_id: str,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET locked_by = NULL, locked_at = NULL WHERE id = ? AND locked_by = ?",
                (job_id, worker_id)
            )
            conn.commit()

    def record_attempt(
        self,
        job_id: str,
    ) -> int:
        with self._get_connection() as conn:
            conn.execute("UPDATE jobs SET attempts = attempts + 1 WHERE id = ?", (job_id,))
            conn.commit()
            row = conn.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()

        return row["attempts"]

    def list_runnable_job_ids(
        self,
        statuses: List[JobStatus],
        limit: int = 50,
        stale_minutes: int = JOB_LOCK_STALE_MINUTES,
    ) -> List[str]:
        """Unlocked (or stale-locked) jobs in the given statuses, oldest first."""
        if not statuses:
            return []

        stale_before = (datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)).isoformat()

        with self._get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id FROM jobs
                WHERE status IN ({", ".join("?" for _ in statuses)})
                  AND (locked_by IS NULL OR locked_at < ?)
                  -- review gates: translation needs a target page, voicing needs an approved translation
                  AND (status != 'transcribed' OR page_id IS NOT NULL)
                  AND (status != 'translated' OR translation_approved = 1)
                  AND (status != 'rendered' OR render_approved = 1)
                ORDER BY updated_at
                LIMIT ?
                """,
                (*[s.value for s in statuses], stale_before, limit)
            ).fetchall()

        return [r["id"] for r in rows]

    def set_local_only(
        self,
        job_id: str,
        local_only: Optional[bool],
    ) -> Job:
        self.get_job(job_id)

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET local_only = ?, updated_at = ? WHERE id = ?",
                (None if local_only is None else int(local_only), _now(), job_id)
            )
            conn.commit()

        return self.get_job(job_id)

    def set_render_approved(
        self,
        job_id: str,
        approved: bool,
    ) -> Job:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET render_approved = ?, updated_at = ? WHERE id = ?",
                (int(approved), _now(), job_id)
            )
            conn.commit()

        return self.get_job(job_id)

    def set_translation_approved(
        self,
        job_id: str,
        approved: bool,
    ) -> Job:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET translation_approved = ?, updated_at = ? WHERE id = ?",
                (int(approved), _now(), job_id)
            )
            conn.commit()

        return self.get_job(job_id)

    def assign_page(
        self,
        job_id: str,
        page_id: int,
    ) -> Job:
        job = self.get_job(job_id)

        if not self.get_page(page_id):
            raise NotFoundError(f"Page profile {page_id} not found.")

        stage = job.failed_from if job.status == JobStatus.FAILED else job.status

        if stage in PIPELINE_STAGES and PIPELINE_STAGES.index(stage) >= PIPELINE_STAGES.index(PAGE_REQUIRED_FROM):
            raise InvalidTransitionError("The target page can only change before translation; move the job back first.")

        with self._get_connection() as conn:
            try:
                conn.execute(
                    "UPDATE jobs SET page_id = ?, updated_at = ? WHERE id = ?",
                    (page_id, _now(), job_id)
                )
            except sqlite3.IntegrityError as err:
                raise InvalidTransitionError(f"Source '{job.source_key}' already has a job for page {page_id}.") from err

            conn.commit()

        return self.get_job(job_id)

    def set_artifact(
        self,
        job_id: str,
        name: str,
        path: str,
    ) -> Job:
        job = self.get_job(job_id)
        artifacts = {**job.artifacts, name: path}

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET artifacts_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(artifacts), _now(), job_id)
            )
            conn.commit()

        return self.get_job(job_id)

    def get_job_events(
        self,
        job_id: str,
    ) -> List[JobEvent]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY id",
                (job_id,)
            ).fetchall()

        return [
            JobEvent(
                job_id=r["job_id"],
                from_status=JobStatus(r["from_status"]) if r["from_status"] else None,
                to_status=JobStatus(r["to_status"]),
                note=r["note"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def lane_counts(self) -> Dict[str, int]:
        """
        Jobs per pipeline lane (discarded jobs excluded):
          needs_you  translated and waiting for translation approval, rendered and waiting for render approval
          working    everything between found and rendered that is moving (incl. approved, waiting for the worker)
          failed     failed jobs
          done       exported jobs
        """
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN (status = 'translated' AND translation_approved = 0)
                               OR (status = 'rendered' AND render_approved = 0) THEN 1 ELSE 0 END) AS needs_you,
                    SUM(CASE WHEN status IN ('found', 'downloaded', 'transcribed', 'voiced')
                               OR (status = 'translated' AND translation_approved = 1)
                               OR (status = 'rendered' AND render_approved = 1) THEN 1 ELSE 0 END) AS working,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN status = 'exported' THEN 1 ELSE 0 END) AS done
                FROM jobs
                """
            ).fetchone()

        return {k: int(row[k] or 0) for k in ("needs_you", "working", "failed", "done")}

    def count_jobs_by_status(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()

        return {r["status"]: r["n"] for r in rows}

    # ------------------------------------------------------------ page profiles

    @staticmethod
    def _row_to_page(row: sqlite3.Row) -> PageProfile:
        return PageProfile(
            id=row["id"],
            display_name=row["display_name"],
            handle=row["handle"],
            avatar_path=row["avatar_path"],
            language=row["language"],
            template_id=row["template_id"],
            default_hashtags=json.loads(row["default_hashtags_json"]) if row["default_hashtags_json"] else [],
            caption_footer=row["caption_footer"],
            tts_voice=row["tts_voice"],
            auto_approve_translation=bool(row["auto_approve_translation"]),
            auto_approve_render=bool(row["auto_approve_render"]),
            local_only=bool(row["local_only"]),
            niche=row["niche"],
            brand_tag=row["brand_tag"],
            glossary=json.loads(row["glossary_json"]) if row["glossary_json"] else [],
            outputs=json.loads(row["outputs_json"]) if row["outputs_json"] else ["reel"],
            audio_bed_path=row["audio_bed_path"],
            active=bool(row["active"]),
        )

    def save_page(
        self,
        page: PageProfile,
    ) -> PageProfile:
        """Creates a page profile, or updates it when page.id is set."""
        if page.template_id is not None and not self.get_template(page.template_id):
            raise NotFoundError(f"Render template {page.template_id} not found.")

        now = _now()
        values = (
            page.display_name, page.handle.lstrip("@"), page.avatar_path, page.language, page.template_id,
            json.dumps(page.default_hashtags), page.caption_footer, page.tts_voice,
            int(page.auto_approve_translation), int(page.local_only), page.niche, page.brand_tag,
            json.dumps(page.glossary), json.dumps(page.outputs), page.audio_bed_path, int(page.auto_approve_render),
            int(page.active),
        )

        with self._get_connection() as conn:
            if page.id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO page_profiles (
                        display_name, handle, avatar_path, language, template_id,
                        default_hashtags_json, caption_footer, tts_voice, auto_approve_translation,
                        local_only, niche, brand_tag, glossary_json, outputs_json, audio_bed_path,
                        auto_approve_render, active, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*values, now, now)
                )
                page_id = cursor.lastrowid
            else:
                cursor = conn.execute(
                    """
                    UPDATE page_profiles SET
                        display_name = ?, handle = ?, avatar_path = ?, language = ?, template_id = ?,
                        default_hashtags_json = ?, caption_footer = ?, tts_voice = ?,
                        auto_approve_translation = ?, local_only = ?, niche = ?, brand_tag = ?,
                        glossary_json = ?, outputs_json = ?, audio_bed_path = ?, auto_approve_render = ?,
                        active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (*values, now, page.id)
                )

                if cursor.rowcount == 0:
                    raise NotFoundError(f"Page profile {page.id} not found.")

                page_id = page.id

            conn.commit()

        return self.get_page(page_id)

    def get_page(
        self,
        page_id: int,
    ) -> Optional[PageProfile]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM page_profiles WHERE id = ?", (page_id,)).fetchone()

        return self._row_to_page(row) if row else None

    def list_pages(
        self,
        active_only: bool = False,
    ) -> List[PageProfile]:
        query = "SELECT * FROM page_profiles"

        if active_only:
            query += " WHERE active = 1"

        with self._get_connection() as conn:
            rows = conn.execute(query + " ORDER BY display_name").fetchall()

        return [self._row_to_page(r) for r in rows]

    def delete_page(
        self,
        page_id: int,
    ) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM page_profiles WHERE id = ?", (page_id,))
            conn.commit()

        return cursor.rowcount > 0

    # ---------------------------------------------------------- render templates

    @staticmethod
    def _row_to_template(row: sqlite3.Row) -> RenderTemplate:
        config = json.loads(row["config_json"])
        return RenderTemplate(**{**config, "id": row["id"], "name": row["name"]})

    def save_template(
        self,
        template: RenderTemplate,
    ) -> RenderTemplate:
        """Creates a render template, or updates it when template.id is set."""
        now = _now()
        config_json = json.dumps(template.model_dump(exclude={"id", "name"}))

        with self._get_connection() as conn:
            if template.id is None:
                cursor = conn.execute(
                    "INSERT INTO render_templates (name, config_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (template.name, config_json, now, now)
                )
                template_id = cursor.lastrowid
            else:
                cursor = conn.execute(
                    "UPDATE render_templates SET name = ?, config_json = ?, updated_at = ? WHERE id = ?",
                    (template.name, config_json, now, template.id)
                )

                if cursor.rowcount == 0:
                    raise NotFoundError(f"Render template {template.id} not found.")

                template_id = template.id

            conn.commit()

        return self.get_template(template_id)

    def get_template(
        self,
        template_id: int,
    ) -> Optional[RenderTemplate]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM render_templates WHERE id = ?", (template_id,)).fetchone()

        return self._row_to_template(row) if row else None

    def list_templates(self) -> List[RenderTemplate]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM render_templates ORDER BY name").fetchall()

        return [self._row_to_template(r) for r in rows]


pipeline_repo = PipelineRepository()
