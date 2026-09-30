from __future__ import annotations

import sqlite3
from typing import Callable, List, Tuple

from underfind.backend.core.logger import logger


def _table_exists(
    conn: sqlite3.Connection,
    table: str,
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,)
    ).fetchone()
    return row is not None


def _column_exists(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> bool:
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _v1_localization_pipeline(conn: sqlite3.Connection) -> None:
    """Source videos, jobs state machine, page profiles, render templates, quota and query membership."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_videos (
            source_key TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            source_id TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            caption TEXT,
            author_handle TEXT,
            author_name TEXT,
            thumbnail_url TEXT,
            views INTEGER,
            likes INTEGER,
            comments_count INTEGER,
            followers INTEGER,
            duration_seconds INTEGER,
            published_at TEXT,
            language TEXT,
            phash TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS render_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS page_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            handle TEXT UNIQUE NOT NULL,
            avatar_path TEXT,
            language TEXT NOT NULL,
            template_id INTEGER REFERENCES render_templates(id) ON DELETE SET NULL,
            default_hashtags_json TEXT,
            caption_footer TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            source_key TEXT NOT NULL REFERENCES source_videos(source_key),
            page_id INTEGER REFERENCES page_profiles(id) ON DELETE SET NULL,
            status TEXT NOT NULL,
            failed_from TEXT,
            error TEXT,
            mode TEXT NOT NULL,
            artifacts_json TEXT,
            notes TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            from_status TEXT,
            to_status TEXT NOT NULL,
            note TEXT,
            created_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_quota (
            provider TEXT NOT NULL,
            day TEXT NOT NULL,
            units_used INTEGER NOT NULL DEFAULT 0,
            exhausted INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (provider, day)
        )
    """)

    # A video can belong to several cached queries; videos.query_key only kept the last one.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_videos (
            query_key TEXT NOT NULL,
            video_id TEXT NOT NULL,
            PRIMARY KEY (query_key, video_id)
        )
    """)

    if _table_exists(conn, "videos"):
        conn.execute("""
            INSERT OR IGNORE INTO query_videos (query_key, video_id)
            SELECT query_key, video_id FROM videos WHERE query_key IS NOT NULL
        """)

    if _table_exists(conn, "ideas_board") and not _column_exists(conn, "ideas_board", "job_id"):
        conn.execute("ALTER TABLE ideas_board ADD COLUMN job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source_key)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_source_page ON jobs(source_key, page_id) WHERE page_id IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source_videos_phash ON source_videos(phash) WHERE phash IS NOT NULL")


def _v2_worker_and_media(conn: sqlite3.Connection) -> None:
    """Worker claim/lock + attempt counter on jobs, on-screen text flag on sources."""
    if not _column_exists(conn, "jobs", "attempts"):
        conn.execute("ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")

    if not _column_exists(conn, "jobs", "locked_by"):
        conn.execute("ALTER TABLE jobs ADD COLUMN locked_by TEXT")

    if not _column_exists(conn, "jobs", "locked_at"):
        conn.execute("ALTER TABLE jobs ADD COLUMN locked_at TIMESTAMP")

    if not _column_exists(conn, "source_videos", "has_onscreen_text"):
        conn.execute("ALTER TABLE source_videos ADD COLUMN has_onscreen_text INTEGER")


def _v3_translation_review(conn: sqlite3.Connection) -> None:
    """Translation review gate on jobs; TTS voice and auto-approval per page."""
    if not _column_exists(conn, "jobs", "translation_approved"):
        conn.execute("ALTER TABLE jobs ADD COLUMN translation_approved INTEGER NOT NULL DEFAULT 0")

    if not _column_exists(conn, "page_profiles", "tts_voice"):
        conn.execute("ALTER TABLE page_profiles ADD COLUMN tts_voice TEXT")

    if not _column_exists(conn, "page_profiles", "auto_approve_translation"):
        conn.execute("ALTER TABLE page_profiles ADD COLUMN auto_approve_translation INTEGER NOT NULL DEFAULT 0")


def _v4_local_only(conn: sqlite3.Connection) -> None:
    """"Local only" checkbox on pages (default checked) and an optional per-job override."""
    if not _column_exists(conn, "page_profiles", "local_only"):
        conn.execute("ALTER TABLE page_profiles ADD COLUMN local_only INTEGER NOT NULL DEFAULT 1")

    if not _column_exists(conn, "jobs", "local_only"):
        conn.execute("ALTER TABLE jobs ADD COLUMN local_only INTEGER")


MIGRATIONS: List[Tuple[int, Callable[[sqlite3.Connection], None]]] = [
    (1, _v1_localization_pipeline),
    (2, _v2_worker_and_media),
    (3, _v3_translation_review),
    (4, _v4_local_only),
]


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Applies pending schema migrations tracked by PRAGMA user_version. Returns the resulting version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]

    for version, migrate in MIGRATIONS:
        if version <= current:
            continue

        logger.info("Applying SQLite schema migration v%d (%s)", version, migrate.__name__)
        migrate(conn)
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()
        current = version

    return current
