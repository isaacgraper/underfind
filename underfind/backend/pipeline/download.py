from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from underfind.backend.core.constants import YTDLP_FORMAT
from underfind.backend.core.errors import PermanentStageError
from underfind.backend.core.logger import logger

# Failures that retrying won't fix. Login walls need cookies configured, not another attempt.
_PERMANENT_MARKERS = (
    "private",
    "removed",
    "deleted",
    "does not exist",
    "not available",
    "unavailable",
    "login required",
    "log in",
    "sign in to confirm",
    "copyright",
    "unsupported url",
    "http error 404",
)


@dataclass
class DownloadResult:
    video_path: Path
    info: Dict[str, Any]


def source_updates_from_info(info: Dict[str, Any]) -> Dict[str, Any]:
    """Maps yt-dlp metadata onto SourceVideo fields (only the values yt-dlp actually returned)."""
    published_at: Optional[str] = None

    if info.get("timestamp"):
        published_at = datetime.fromtimestamp(info["timestamp"], tz=timezone.utc).isoformat()
    elif info.get("upload_date"):
        raw = str(info["upload_date"])
        published_at = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T00:00:00+00:00"

    duration = info.get("duration")
    updates = {
        "title": info.get("title"),
        "caption": info.get("description"),
        "author_handle": info.get("uploader_id") or info.get("channel_id") or info.get("uploader"),
        "author_name": info.get("uploader") or info.get("channel"),
        "thumbnail_url": info.get("thumbnail"),
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "comments_count": info.get("comment_count"),
        "followers": info.get("channel_follower_count"),
        "duration_seconds": int(round(duration)) if duration else None,
        "published_at": published_at,
    }
    return {k: v for k, v in updates.items() if v is not None}


class YtDlpDownloader:
    """
    Downloads one video (YouTube, Instagram, TikTok) with yt-dlp as source.mp4.
    Configure via env for platforms that wall anonymous requests:
      YTDLP_COOKIES_FILE          Netscape cookies.txt exported from a logged-in browser
      YTDLP_COOKIES_FROM_BROWSER  e.g. "chrome" or "firefox" (reads cookies from the local browser profile)
      YTDLP_PROXY                 e.g. "http://user:pass@host:port"
    """

    def __init__(
        self,
        cookies_file: Optional[str] = None,
        cookies_from_browser: Optional[str] = None,
        proxy: Optional[str] = None,
        ffmpeg_location: Optional[str] = None,
    ):
        self.cookies_file = cookies_file or os.environ.get("YTDLP_COOKIES_FILE") or None
        self.cookies_from_browser = cookies_from_browser or os.environ.get("YTDLP_COOKIES_FROM_BROWSER") or None
        self.proxy = proxy or os.environ.get("YTDLP_PROXY") or None
        self.ffmpeg_location = ffmpeg_location

    def _options(self, dest_dir: Path) -> Dict[str, Any]:
        from underfind.backend.pipeline.media import ffmpeg_exe

        opts: Dict[str, Any] = {
            "format": YTDLP_FORMAT,
            "merge_output_format": "mp4",
            "outtmpl": str(dest_dir / "source.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "ffmpeg_location": self.ffmpeg_location or ffmpeg_exe(),
        }

        if self.cookies_file:
            opts["cookiefile"] = self.cookies_file

        if self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)

        if self.proxy:
            opts["proxy"] = self.proxy

        return opts

    def download(
        self,
        url: str,
        dest_dir: Path,
    ) -> DownloadResult:
        import yt_dlp
        from yt_dlp.utils import DownloadError

        dest_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading %s", url)

        try:
            with yt_dlp.YoutubeDL(self._options(dest_dir)) as ydl:
                info = ydl.sanitize_info(ydl.extract_info(url, download=True))

        except DownloadError as err:
            message = str(err)

            if any(marker in message.lower() for marker in _PERMANENT_MARKERS):
                hint = "" if (self.cookies_file or self.cookies_from_browser) else " Configure YTDLP_COOKIES_FILE if the platform requires login."
                raise PermanentStageError(f"Download failed: {message}{hint}") from err

            raise

        video_path = dest_dir / "source.mp4"

        if not video_path.exists():
            candidates = sorted(p for p in dest_dir.glob("source.*") if p.suffix not in (".json", ".part"))

            if not candidates:
                raise RuntimeError(f"yt-dlp reported success but no file was written for {url}")

            candidates[0].rename(video_path)

        (dest_dir / "meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return DownloadResult(video_path=video_path, info=info)
