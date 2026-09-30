from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from underfind.backend.core.constants import (
    DATABASE_PATH,
    DEFAULT_TTL_HOURS,
    DEFAULT_REGION,
    DEFAULT_IDEA_STATUS,
    DEFAULT_SHOWCASE_LIMIT,
)
from underfind.backend.schemas.video import VideoItem
from underfind.backend.schemas.blueprint import VideoBlueprint, TranscriptLine
from underfind.backend.core.logger import logger
from underfind.backend.db.migrations import apply_migrations


class CacheManager:
    """
    Local SQLite Cache Manager for:
    1. Permanent search and video caching for zero-bandwidth API quota preservation.
    2. Processed AI blueprints and transcript caching.
    3. Production ideas Kanban board (Backlog, In Progress, Done).
    """

    def __init__(
        self,
        db_path: Path = DATABASE_PATH,
    ):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_queries (
                    query_key TEXT PRIMARY KEY,
                    query TEXT,
                    is_shorts INTEGER,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    title TEXT,
                    channel_id TEXT,
                    channel_title TEXT,
                    thumbnail_url TEXT,
                    views INTEGER,
                    likes INTEGER,
                    comments_count INTEGER,
                    subscribers INTEGER,
                    duration_seconds INTEGER,
                    published_at TEXT,
                    video_url TEXT,
                    is_short INTEGER,
                    viral_ratio REAL,
                    description TEXT,
                    tags_json TEXT,
                    query_key TEXT,
                    cached_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS blueprints (
                    video_id TEXT PRIMARY KEY,
                    title TEXT,
                    channel_title TEXT,
                    views INTEGER,
                    subscribers INTEGER,
                    viral_ratio REAL,
                    video_url TEXT,
                    duration_seconds INTEGER,
                    is_short INTEGER,
                    hook_text TEXT,
                    hook_duration REAL,
                    full_transcript TEXT,
                    segments_json TEXT,
                    suggested_prompt TEXT,
                    cached_at TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ideas_board (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT UNIQUE,
                    title TEXT,
                    channel_title TEXT,
                    thumbnail_url TEXT,
                    views INTEGER,
                    subscribers INTEGER,
                    viral_ratio REAL,
                    duration_seconds INTEGER,
                    video_url TEXT,
                    status TEXT DEFAULT 'backlog',
                    hook_text TEXT,
                    script_notes TEXT,
                    job_id TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_query ON videos(query_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_ratio ON videos(viral_ratio DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas_board(status)")
            conn.commit()

            apply_migrations(conn)

    @staticmethod
    def generate_query_key(
        query: str,
        is_shorts: bool,
        region: str = DEFAULT_REGION,
    ) -> str:
        clean_q = query.lower().strip()
        return f"{region}:{int(is_shorts)}:{clean_q}"

    def get_cached_videos(
        self,
        query_key: str,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> Optional[List[VideoItem]]:
        """Returns cached video items if the query has been performed previously."""
        logger.debug("Checking SQLite cache for query key: '%s'", query_key)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT updated_at FROM search_queries WHERE query_key = ?",
                (query_key,)
            )
            row = cursor.fetchone()

            if not row:
                logger.trace("Cache MISS for query key: '%s'", query_key)
                return None

            updated_at = datetime.fromisoformat(row["updated_at"])

            if datetime.now(timezone.utc) - updated_at > timedelta(hours=ttl_hours):
                logger.debug("Cache EXPIRED for query key: '%s'", query_key)
                return None

            cursor.execute(
                """
                SELECT v.* FROM videos v
                JOIN query_videos qv ON qv.video_id = v.video_id
                WHERE qv.query_key = ?
                ORDER BY v.viral_ratio DESC
                """,
                (query_key,)
            )
            rows = cursor.fetchall()

            if not rows:
                return None

            results: List[VideoItem] = []

            for r in rows:
                tags = json.loads(r["tags_json"]) if r["tags_json"] else []
                results.append(
                    VideoItem(
                        video_id=r["video_id"],
                        title=r["title"],
                        channel_id=r["channel_id"],
                        channel_title=r["channel_title"],
                        thumbnail_url=r["thumbnail_url"],
                        views=r["views"],
                        likes=r["likes"],
                        comments_count=r["comments_count"],
                        subscribers=r["subscribers"],
                        duration_seconds=r["duration_seconds"],
                        published_at=r["published_at"],
                        video_url=r["video_url"],
                        is_short=bool(r["is_short"]),
                        viral_ratio=r["viral_ratio"] or 0.0,
                        description=r["description"],
                        tags=tags,
                    )
                )

            logger.trace("SQLite cache returned %d videos for '%s'", len(results), query_key)
            return results

    def save_videos(
        self,
        query_key: str,
        query: str,
        is_shorts: bool,
        videos: List[VideoItem],
    ) -> None:
        """Saves videos into the permanent SQLite cache indexed by query key."""
        logger.debug("Saving %d videos to SQLite cache for query key: '%s'", len(videos), query_key)
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO search_queries (query_key, query, is_shorts, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(query_key) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (query_key, query, int(is_shorts), now, now)
            )

            for v in videos:
                tags_json = json.dumps(v.tags or [])
                conn.execute(
                    """
                    INSERT INTO videos (
                        video_id, title, channel_id, channel_title, thumbnail_url,
                        views, likes, comments_count, subscribers, duration_seconds,
                        published_at, video_url, is_short, viral_ratio, description,
                        tags_json, query_key, cached_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        views = excluded.views,
                        likes = excluded.likes,
                        subscribers = excluded.subscribers,
                        viral_ratio = excluded.viral_ratio,
                        query_key = excluded.query_key,
                        cached_at = excluded.cached_at
                    """,
                    (
                        v.video_id, v.title, v.channel_id, v.channel_title, v.thumbnail_url,
                        v.views, v.likes, v.comments_count, v.subscribers, v.duration_seconds,
                        v.published_at, v.video_url, int(v.is_short), v.viral_ratio, v.description,
                        tags_json, query_key, now
                    )
                )
                conn.execute(
                    "INSERT OR IGNORE INTO query_videos (query_key, video_id) VALUES (?, ?)",
                    (query_key, v.video_id)
                )

            conn.commit()
            logger.trace("Permanently committed %d videos to SQLite database for '%s'", len(videos), query_key)

    def get_top_performing_videos(
        self,
        limit: int = DEFAULT_SHOWCASE_LIMIT,
    ) -> List[VideoItem]:
        """Returns the highest Viral Ratio cached videos for the dashboard showcase."""
        logger.debug("Retrieving top %d outliers from SQLite cache", limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM videos 
                ORDER BY viral_ratio DESC, views DESC 
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            results: List[VideoItem] = []

            for r in rows:
                tags = json.loads(r["tags_json"]) if r["tags_json"] else []
                results.append(
                    VideoItem(
                        video_id=r["video_id"],
                        title=r["title"],
                        channel_id=r["channel_id"],
                        channel_title=r["channel_title"],
                        thumbnail_url=r["thumbnail_url"],
                        views=r["views"],
                        likes=r["likes"],
                        comments_count=r["comments_count"],
                        subscribers=r["subscribers"],
                        duration_seconds=r["duration_seconds"],
                        published_at=r["published_at"],
                        video_url=r["video_url"],
                        is_short=bool(r["is_short"]),
                        viral_ratio=r["viral_ratio"] or 0.0,
                        description=r["description"],
                        tags=tags,
                    )
                )

            logger.trace("Loaded %d top outliers from SQLite", len(results))
            return results

    def get_cached_blueprint(
        self,
        video_id: str,
    ) -> Optional[VideoBlueprint]:
        logger.debug("Checking SQLite cache for blueprint of video: %s", video_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM blueprints WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()

            if not row:
                logger.trace("Blueprint cache MISS for video: %s", video_id)
                return None

            segments_raw = json.loads(row["segments_json"]) if row["segments_json"] else []
            segments = [
                TranscriptLine(
                    text=s.get("text", ""),
                    start=s.get("start", 0.0),
                    duration=s.get("duration", 0.0)
                )
                for s in segments_raw
            ]

            bp = VideoBlueprint(
                video_id=row["video_id"],
                title=row["title"],
                channel_title=row["channel_title"],
                views=row["views"],
                subscribers=row["subscribers"],
                viral_ratio=row["viral_ratio"] or 0.0,
                video_url=row["video_url"],
                duration_seconds=row["duration_seconds"],
                is_short=bool(row["is_short"]),
                hook_text=row["hook_text"] or "",
                hook_duration=row["hook_duration"] or 0.0,
                full_transcript=row["full_transcript"] or "",
                transcript_segments=segments,
                suggested_prompt=row["suggested_prompt"] or ""
            )

            logger.trace("Blueprint cache HIT for video: %s", video_id)
            return bp

    def save_blueprint(
        self,
        bp: VideoBlueprint,
    ) -> None:
        logger.debug("Saving blueprint for video %s to SQLite cache", bp.video_id)
        now = datetime.now(timezone.utc).isoformat()
        segments_json = json.dumps([s.model_dump() for s in bp.transcript_segments])

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO blueprints (
                    video_id, title, channel_title, views, subscribers, viral_ratio,
                    video_url, duration_seconds, is_short, hook_text, hook_duration,
                    full_transcript, segments_json, suggested_prompt, cached_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    hook_text = excluded.hook_text,
                    full_transcript = excluded.full_transcript,
                    suggested_prompt = excluded.suggested_prompt,
                    cached_at = excluded.cached_at
                """,
                (
                    bp.video_id, bp.title, bp.channel_title, bp.views, bp.subscribers, bp.viral_ratio,
                    bp.video_url, bp.duration_seconds, int(bp.is_short), bp.hook_text, bp.hook_duration,
                    bp.full_transcript, segments_json, bp.suggested_prompt, now
                )
            )
            conn.commit()
            logger.trace("Blueprint for video %s committed to SQLite cache", bp.video_id)

    def get_all_ideas(self) -> List[Dict[str, Any]]:
        """Returns all ideas stored in the Kanban board ordered by updated_at."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ideas_board ORDER BY updated_at DESC"
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def save_idea(
        self,
        video: VideoItem,
        status: str = DEFAULT_IDEA_STATUS,
        hook_text: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Saves a video as an actionable idea in the Kanban board."""
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ideas_board (
                    video_id, title, channel_title, thumbnail_url, views,
                    subscribers, viral_ratio, duration_seconds, video_url,
                    status, hook_text, script_notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title = excluded.title,
                    views = excluded.views,
                    viral_ratio = excluded.viral_ratio,
                    updated_at = excluded.updated_at
                """,
                (
                    video.video_id, video.title, video.channel_title, video.thumbnail_url,
                    video.views, video.subscribers, video.viral_ratio, video.duration_seconds,
                    video.video_url, status, hook_text, notes, now, now
                )
            )
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ideas_board WHERE video_id = ?", (video.video_id,))
            saved = dict(cursor.fetchone())

            logger.trace("Saved idea to Kanban (%s) for video %s", status, video.video_id)
            return saved

    def update_idea_status(
        self,
        video_id: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Moves an idea card across the Kanban pipeline: 'backlog' -> 'in_progress' -> 'done'."""
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            if notes is not None:
                conn.execute(
                    "UPDATE ideas_board SET status = ?, script_notes = ?, updated_at = ? WHERE video_id = ?",
                    (new_status, notes, now, video_id)
                )
            else:
                conn.execute(
                    "UPDATE ideas_board SET status = ?, updated_at = ? WHERE video_id = ?",
                    (new_status, now, video_id)
                )

            conn.commit()
            success = conn.total_changes > 0
            logger.trace("Updated idea status for %s to %s (success=%s)", video_id, new_status, success)
            return success

    def delete_idea(
        self,
        video_id: str,
    ) -> bool:
        """Removes an idea from the Kanban board."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM ideas_board WHERE video_id = ?", (video_id,))
            conn.commit()
            success = conn.total_changes > 0
            logger.trace("Deleted idea for video %s (success=%s)", video_id, success)
            return success

    def seed_starter_outliers_if_empty(self) -> None:
        """Seeds curated high-performing outliers so the dashboard is immediately animated and informative."""
        with self._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]

            if count > 0:
                return

        starter_videos = [
            VideoItem(
                video_id="kJQP7kiw5Fk",
                title="The Psychology Trick That Stops People From Scrolling",
                channel_title="Creator Blueprint Lab",
                thumbnail_url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80",
                views=1280000,
                likes=98400,
                comments_count=1840,
                subscribers=27000,
                duration_seconds=42,
                viral_ratio=47.4,
                video_url="https://youtube.com/shorts/kJQP7kiw5Fk",
                is_short=True,
                description="Breakdown of visual pattern interruption hooks in vertical short-form video."
            ),
            VideoItem(
                video_id="fJ9rUzIMcZQ",
                title="Why 99% Of People Fail At Building Habits (Atomic Rule)",
                channel_title="Focus Systems",
                thumbnail_url="https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=600&auto=format&fit=crop&q=80",
                views=854000,
                likes=64200,
                comments_count=980,
                subscribers=18200,
                duration_seconds=53,
                viral_ratio=46.9,
                video_url="https://youtube.com/shorts/fJ9rUzIMcZQ",
                is_short=True,
                description="Counterintuitive psychological friction model explained in 50 seconds."
            ),
            VideoItem(
                video_id="3JZ_D3ELwOQ",
                title="Secret AI Tool That Edits Podcasts Automatically In 3 Minutes",
                channel_title="Automation Archive",
                thumbnail_url="https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop&q=80",
                views=640000,
                likes=52100,
                comments_count=1230,
                subscribers=15400,
                duration_seconds=38,
                viral_ratio=41.5,
                video_url="https://youtube.com/shorts/3JZ_D3ELwOQ",
                is_short=True,
                description="Rapid workflow demo with high retention pacing."
            ),
            VideoItem(
                video_id="9bZkp7q19f0",
                title="This Financial Concept Will Ruin Your 20s If You Ignore It",
                channel_title="Capital Insight",
                thumbnail_url="https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=600&auto=format&fit=crop&q=80",
                views=590000,
                likes=41000,
                comments_count=890,
                subscribers=19800,
                duration_seconds=49,
                viral_ratio=29.8,
                video_url="https://youtube.com/shorts/9bZkp7q19f0",
                is_short=True,
                description="High curiosity gap hook with seamless loop ending."
            ),
        ]
        self.save_videos("starter:1:curated_outliers", "curated outliers", True, starter_videos)

        self.save_idea(
            video=starter_videos[0],
            status="in_progress",
            hook_text="If you notice people scrolling past your videos in under 2 seconds, you are making this one fatal mistake.",
            notes="Model the 0-3s visual split screen technique. Export cuts to MedPy."
        )

        self.save_idea(
            video=starter_videos[1],
            status="backlog",
            hook_text="Stop trying to fix your motivation. Fix your friction point instead.",
            notes="Adapt for developer productivity and coding routines."
        )


cache_manager = CacheManager()
cache_manager.seed_starter_outliers_if_empty()
