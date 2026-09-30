from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# yt-dlp messages for posts that exist but hold images, not video: handed to gallery-dl instead of failing.
_NO_VIDEO_MARKERS = (
    "no video formats found",
    "there is no video in this post",
    "no video in this post",
    "this post does not contain a video",
    "unsupported url: https://www.tiktok.com/@",
)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


class NoVideoInPost(RuntimeError):
    """The post has no video (photo post or image carousel); try an image downloader."""


@dataclass
class DownloadResult:
    video_path: Optional[Path]
    info: Dict[str, Any]
    files: List[Path] = field(default_factory=list)

    @property
    def media_files(self) -> List[Path]:
        return self.files or ([self.video_path] if self.video_path else [])


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

            if any(marker in message.lower() for marker in _NO_VIDEO_MARKERS):
                raise NoVideoInPost(message) from err

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


def _gallery_info(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """gallery-dl post metadata (Instagram/TikTok/...) mapped to the yt-dlp keys source_updates_from_info reads."""
    author = metadata.get("author") if isinstance(metadata.get("author"), dict) else {}
    info: Dict[str, Any] = {
        "description": metadata.get("description") or metadata.get("content") or metadata.get("desc"),
        "uploader_id": metadata.get("username") or author.get("uniqueId"),
        "uploader": metadata.get("fullname") or metadata.get("nickname") or author.get("nickname"),
        "like_count": metadata.get("likes") or metadata.get("digg_count"),
        "comment_count": metadata.get("comments") or metadata.get("comment_count"),
    }
    date = metadata.get("post_date") or metadata.get("date")

    if isinstance(date, str) and re.match(r"\d{4}-\d{2}-\d{2}", date):
        info["timestamp"] = datetime.fromisoformat(date.replace(" ", "T")).replace(tzinfo=timezone.utc).timestamp()

    return {k: v for k, v in info.items() if v is not None}


class GalleryDlDownloader:
    """
    Photo posts and carousels (images and videos) with gallery-dl, saved as media_00.jpg, media_01.mp4, ...
    Reuses YTDLP_COOKIES_FILE and YTDLP_PROXY; Instagram usually needs the cookies.
    """

    def __init__(
        self,
        cookies_file: Optional[str] = None,
        proxy: Optional[str] = None,
        run=subprocess.run,
    ):
        self.cookies_file = cookies_file or os.environ.get("YTDLP_COOKIES_FILE") or None
        self.proxy = proxy or os.environ.get("YTDLP_PROXY") or None
        self._run = run

    def download(self, url: str, dest_dir: Path) -> DownloadResult:
        dest_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, "-m", "gallery_dl",
            "-D", str(dest_dir),
            "-f", "media_{num:>02}.{extension}",
            "--write-metadata",
        ]

        if self.cookies_file:
            cmd += ["-C", self.cookies_file]

        if self.proxy:
            cmd += ["--proxy", self.proxy]

        logger.info("Downloading post media with gallery-dl: %s", url)
        result = self._run([*cmd, url], capture_output=True, text=True, timeout=600)
        files = sorted(
            p for p in dest_dir.glob("media_*")
            if p.suffix.lower() in IMAGE_SUFFIXES | VIDEO_SUFFIXES
        )

        if result.returncode != 0 or not files:
            message = (result.stderr or result.stdout or "").strip()[-500:] or "no media downloaded"

            if any(marker in message.lower() for marker in _PERMANENT_MARKERS) or not files:
                hint = "" if self.cookies_file else " Configure YTDLP_COOKIES_FILE if the platform requires login."
                raise PermanentStageError(f"Post download failed: {message}{hint}")

            raise RuntimeError(f"gallery-dl failed: {message}")

        metadata_files = sorted(dest_dir.glob("media_*.json"))
        metadata = json.loads(metadata_files[0].read_text(encoding="utf-8")) if metadata_files else {}
        info = _gallery_info(metadata)
        (dest_dir / "meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return DownloadResult(video_path=None, info=info, files=files)


# Post URLs that are usually photos or carousels go to gallery-dl first.
_GALLERY_FIRST = re.compile(r"instagram\.com/(?:[A-Za-z0-9_.]+/)?p/|tiktok\.com/@[^/]+/photo/")


class MediaDownloader:
    """yt-dlp for videos; gallery-dl for photo posts and carousels, and whenever yt-dlp finds no video."""

    def __init__(
        self,
        video: Optional[YtDlpDownloader] = None,
        gallery: Optional[GalleryDlDownloader] = None,
    ):
        self.video = video or YtDlpDownloader()
        self.gallery = gallery or GalleryDlDownloader()

    def download(self, url: str, dest_dir: Path) -> DownloadResult:
        if _GALLERY_FIRST.search(url):
            return self.gallery.download(url, dest_dir)

        try:
            return self.video.download(url, dest_dir)
        except NoVideoInPost:
            logger.info("No video in %s; downloading its images", url)
            return self.gallery.download(url, dest_dir)
