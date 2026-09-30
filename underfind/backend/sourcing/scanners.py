from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol

import requests

from underfind.backend.core.logger import logger
from underfind.backend.core.utils import parse_source_url
from underfind.backend.core.niches import Niche
from underfind.backend.schemas.pipeline import Platform, SourceVideo
from underfind.backend.schemas.video import SearchRequest
from underfind.backend.services.job_service import JobService


class Scanner(Protocol):
    name: str
    seed: bool  # posts come from a hand-picked on-topic page

    def scan(self, niche: Niche) -> List[SourceVideo]:
        ...


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


# ------------------------------------------------------------------ YouTube


class YouTubeKeywordScanner:
    """
    Shorts search over the niche's keywords x regions (search.list = 100 quota units each). Rotates through the
    keyword/region pairs across scans so every pair gets its turn within the per-scan search budget.
    """

    seed = False

    def __init__(self, service: Any, rotation: int = 0):
        self.service = service
        self.rotation = rotation
        self.name = "youtube_keywords"

    def pairs(self, niche: Niche) -> List[tuple[str, str]]:
        regions = niche.regions or ["US"]
        all_pairs = [(k, r) for k in niche.keywords.include for r in regions]

        if not all_pairs or niche.scan.youtube_keyword_searches <= 0:
            return []

        start = (self.rotation * niche.scan.youtube_keyword_searches) % len(all_pairs)
        ordered = all_pairs[start:] + all_pairs[:start]
        return ordered[:niche.scan.youtube_keyword_searches]

    def scan(self, niche: Niche) -> List[SourceVideo]:
        found: List[SourceVideo] = []

        for keyword, region in self.pairs(niche):
            req = SearchRequest(
                query=keyword,
                is_shorts_only=True,
                order="viewCount",
                published_after_days=niche.scan.max_age_days,
                region_code=region,
                max_results=niche.scan.per_source_limit,
                force_refresh=True,
            )
            found.extend(JobService.source_from_video_item(v) for v in self.service.search(req))

        return found


class YouTubeChannelScanner:
    """Recent uploads of one seed channel (~4 quota units)."""

    seed = True

    def __init__(self, service: Any, channel: str):
        self.service = service
        self.channel = channel
        self.name = f"youtube_channel:{channel}"

    def scan(self, niche: Niche) -> List[SourceVideo]:
        videos = self.service.channel_recent_videos(self.channel, limit=niche.scan.per_source_limit)
        return [JobService.source_from_video_item(v) for v in videos]


# ------------------------------------------------------------------ Instagram


def _parse_graph_time(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    try:
        return _iso(datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z"))
    except ValueError:
        return value


class InstagramGraphScanner:
    """
    Official, free Instagram Graph API "Business Discovery": recent posts of a public business/creator account.
    Needs your own professional account id and a token: IG_GRAPH_USER_ID, IG_GRAPH_TOKEN. No view counts
    (scoring estimates them from likes).
    """

    seed = True
    api = "https://graph.facebook.com/v21.0"

    def __init__(
        self,
        username: str,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
        get: Callable[..., Any] = requests.get,
    ):
        self.username = username.lstrip("@")
        self.user_id = user_id or os.environ.get("IG_GRAPH_USER_ID", "")
        self.token = token or os.environ.get("IG_GRAPH_TOKEN", "")
        self._get = get
        self.name = f"instagram:{self.username}"

    @classmethod
    def configured(cls) -> bool:
        return bool(os.environ.get("IG_GRAPH_USER_ID") and os.environ.get("IG_GRAPH_TOKEN"))

    def scan(self, niche: Niche) -> List[SourceVideo]:
        fields = (
            f"business_discovery.username({self.username}){{followers_count,username,name,"
            f"media.limit({niche.scan.per_source_limit}){{id,caption,media_type,media_product_type,permalink,"
            f"timestamp,like_count,comments_count}}}}"
        )
        res = self._get(f"{self.api}/{self.user_id}", params={"fields": fields, "access_token": self.token}, timeout=30)
        data = res.json()

        if res.status_code >= 400 or "error" in data:
            raise RuntimeError(f"Graph API error for @{self.username}: {data.get('error', {}).get('message', res.status_code)}")

        account = data.get("business_discovery", {})
        followers = account.get("followers_count")
        found: List[SourceVideo] = []

        for media in account.get("media", {}).get("data", []):
            permalink = media.get("permalink") or ""

            try:
                platform, source_id = parse_source_url(permalink)
            except ValueError:
                continue

            found.append(SourceVideo(
                platform=Platform(platform),
                source_id=source_id,
                url=permalink,
                caption=media.get("caption"),
                author_handle=account.get("username") or self.username,
                author_name=account.get("name"),
                likes=media.get("like_count"),
                comments_count=media.get("comments_count"),
                followers=followers,
                published_at=_parse_graph_time(media.get("timestamp")),
            ))

        return found


class InstagramGalleryScanner:
    """
    Fallback without a Graph token: lists a profile's recent posts with gallery-dl (metadata only, nothing
    downloaded). Instagram requires login cookies for this: YTDLP_COOKIES_FILE.
    """

    seed = True

    def __init__(self, username: str, run: Callable[..., Any] = subprocess.run):
        self.username = username.lstrip("@")
        self._run = run
        self.name = f"instagram:{self.username}"

    def scan(self, niche: Niche) -> List[SourceVideo]:
        cmd = [
            sys.executable, "-m", "gallery_dl", "--dump-json", "--range", f"1-{niche.scan.per_source_limit * 3}",
            f"https://www.instagram.com/{self.username}/posts/",
        ]
        cookies = os.environ.get("YTDLP_COOKIES_FILE")

        if cookies:
            cmd[3:3] = ["-C", cookies]

        result = self._run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0 and not result.stdout.strip():
            raise RuntimeError(f"gallery-dl could not list @{self.username}: {(result.stderr or '').strip()[-300:]}")

        return self.parse(result.stdout, niche.scan.per_source_limit)

    def parse(self, output: str, limit: int) -> List[SourceVideo]:
        """gallery-dl --dump-json prints [message_type, url?, metadata] entries; carousel items share a shortcode."""
        try:
            messages = json.loads(output or "[]")
        except json.JSONDecodeError:
            return []

        merged: Dict[str, Dict[str, Any]] = {}

        for message in messages:
            meta = next((m for m in message if isinstance(m, dict)), None) if isinstance(message, list) else None

            if not meta or not meta.get("post_shortcode"):
                continue

            # Directory and per-file messages of one post carry different fields: keep the first non-empty value.
            post = merged.setdefault(meta["post_shortcode"], {})

            for key, value in meta.items():
                if value not in (None, "") and key not in post:
                    post[key] = value

        posts: List[SourceVideo] = []

        for code, meta in list(merged.items())[:limit]:
            posts.append(SourceVideo(
                platform=Platform.INSTAGRAM,
                source_id=code,
                url=meta.get("post_url") or f"https://www.instagram.com/p/{code}/",
                caption=meta.get("description"),
                author_handle=meta.get("username") or self.username,
                author_name=meta.get("fullname"),
                likes=meta.get("likes"),
                comments_count=meta.get("comments"),
                views=meta.get("video_view_count") or meta.get("view_count"),
                published_at=str(meta["post_date"]).replace(" ", "T") + "+00:00" if meta.get("post_date") else None,
            ))

        return posts


# ------------------------------------------------------------------ TikTok


class TikTokScanner:
    """A TikTok profile's recent videos via yt-dlp's flat listing (no download). May need YTDLP_COOKIES_FILE."""

    seed = True

    def __init__(self, username: str, extract: Optional[Callable[[str, dict], dict]] = None):
        self.username = username.lstrip("@")
        self._extract = extract or self._yt_dlp_extract
        self.name = f"tiktok:{self.username}"

    @staticmethod
    def _yt_dlp_extract(url: str, opts: dict) -> dict:
        import yt_dlp

        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.sanitize_info(ydl.extract_info(url, download=False))

    def scan(self, niche: Niche) -> List[SourceVideo]:
        opts: Dict[str, Any] = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "playlistend": niche.scan.per_source_limit}

        if os.environ.get("YTDLP_COOKIES_FILE"):
            opts["cookiefile"] = os.environ["YTDLP_COOKIES_FILE"]

        info = self._extract(f"https://www.tiktok.com/@{self.username}", opts)
        found: List[SourceVideo] = []

        for entry in (info.get("entries") or [])[:niche.scan.per_source_limit]:
            video_id = str(entry.get("id") or "")

            if not video_id.isdigit():
                continue

            timestamp = entry.get("timestamp")
            found.append(SourceVideo(
                platform=Platform.TIKTOK,
                source_id=video_id,
                url=entry.get("url") if str(entry.get("url", "")).startswith("http") else f"https://www.tiktok.com/@{self.username}/video/{video_id}",
                title=entry.get("title"),
                caption=entry.get("description") or entry.get("title"),
                author_handle=self.username,
                views=entry.get("view_count"),
                likes=entry.get("like_count"),
                comments_count=entry.get("comment_count"),
                followers=entry.get("channel_follower_count"),
                duration_seconds=int(entry["duration"]) if entry.get("duration") else None,
                published_at=_iso(datetime.fromtimestamp(timestamp, tz=timezone.utc)) if timestamp else None,
            ))

        return found


def build_scanners(niche: Niche, youtube: Any = None, rotation: int = 0) -> List[Scanner]:
    """Every scanner the niche's config calls for; YouTube scanners only when an API key is configured."""
    scanners: List[Scanner] = []
    seeds = niche.seed_pages
    youtube_ready = youtube is not None and getattr(youtube, "api_key", "")

    if youtube_ready:
        if niche.keywords.include and niche.scan.youtube_keyword_searches > 0:
            scanners.append(YouTubeKeywordScanner(youtube, rotation))

        scanners.extend(YouTubeChannelScanner(youtube, c) for c in seeds.get("youtube_channels", []))
    elif niche.keywords.include or seeds.get("youtube_channels"):
        logger.info("YouTube scanners skipped for niche %s: YOUTUBE_API_KEY not set", niche.name)

    for user in seeds.get("instagram", []):
        scanners.append(InstagramGraphScanner(user) if InstagramGraphScanner.configured() else InstagramGalleryScanner(user))

    scanners.extend(TikTokScanner(u) for u in seeds.get("tiktok", []))
    return scanners
