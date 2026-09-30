from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from underfind.backend.core.constants import (
    DATABASE_PATH,
    YOUTUBE_DAILY_QUOTA,
    YOUTUBE_QUOTA_TIMEZONE,
)
from underfind.backend.core.errors import QuotaExceededError
from underfind.backend.core.logger import logger
from underfind.backend.db.migrations import apply_migrations
from underfind.backend.schemas.pipeline import QuotaStatus


class QuotaTracker:
    """
    Persistent daily API unit budget per provider.
    YouTube Data API quotas reset at midnight Pacific Time, so the quota day is computed in that zone.
    Units are reserved before each request (the API bills failed requests too).
    """

    def __init__(
        self,
        db_path: Path = DATABASE_PATH,
        provider: str = "youtube",
        daily_limit: int | None = None,
        timezone_name: str = YOUTUBE_QUOTA_TIMEZONE,
    ):
        self.db_path = db_path
        self.provider = provider
        self.daily_limit = daily_limit or int(os.environ.get("YOUTUBE_DAILY_QUOTA", YOUTUBE_DAILY_QUOTA))
        self.tz = ZoneInfo(timezone_name)
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            apply_migrations(conn)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _today(self) -> str:
        return datetime.now(self.tz).date().isoformat()

    def _read(
        self,
        conn: sqlite3.Connection,
        day: str,
    ) -> tuple[int, bool]:
        row = conn.execute(
            "SELECT units_used, exhausted FROM api_quota WHERE provider = ? AND day = ?",
            (self.provider, day)
        ).fetchone()
        return (row["units_used"], bool(row["exhausted"])) if row else (0, False)

    def consume(
        self,
        units: int,
    ) -> int:
        """Reserves units for the current quota day. Raises QuotaExceededError instead of overspending."""
        day = self._today()

        with self._lock, self._get_connection() as conn:
            used, exhausted = self._read(conn, day)

            if exhausted or used + units > self.daily_limit:
                raise QuotaExceededError(self.provider, used, self.daily_limit, units)

            conn.execute(
                """
                INSERT INTO api_quota (provider, day, units_used) VALUES (?, ?, ?)
                ON CONFLICT(provider, day) DO UPDATE SET units_used = units_used + excluded.units_used
                """,
                (self.provider, day, units)
            )
            conn.commit()

        logger.trace("Quota %s: reserved %d units (%d/%d used today)", self.provider, units, used + units, self.daily_limit)
        return used + units

    def mark_exhausted(self) -> None:
        """Flags today's quota as spent after the provider itself reports exhaustion (e.g. shared key used elsewhere)."""
        day = self._today()

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO api_quota (provider, day, units_used, exhausted) VALUES (?, ?, 0, 1)
                ON CONFLICT(provider, day) DO UPDATE SET exhausted = 1
                """,
                (self.provider, day)
            )
            conn.commit()

        logger.warning("Quota %s marked exhausted for %s by the provider.", self.provider, day)

    def status(self) -> QuotaStatus:
        day = self._today()

        with self._get_connection() as conn:
            used, exhausted = self._read(conn, day)

        return QuotaStatus(
            provider=self.provider,
            day=day,
            used=used,
            limit=self.daily_limit,
            remaining=0 if exhausted else max(0, self.daily_limit - used),
            exhausted=exhausted or used >= self.daily_limit,
        )


youtube_quota = QuotaTracker()
