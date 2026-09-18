from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from underfind.backend.core.constants import (
    DEFAULT_REGION,
    DEFAULT_MAX_RESULTS,
    MAX_ALLOWED_RESULTS,
    MAX_STANDARD_SHORT_DURATION,
    MAX_EXTENDED_SHORT_DURATION,
    MIN_SUBSCRIBER_BASE,
)
from underfind.backend.core.utils import parse_iso8601_duration, calculate_viral_ratio
from underfind.backend.db.database import cache_manager
from underfind.backend.schemas.video import VideoItem, SearchRequest, TrendingRequest
from underfind.backend.core.logger import logger


class YouTubeService:
    """Service client for YouTube Data API v3 and Analytics integration."""

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        load_dotenv()
        self.api_key = (
            api_key
            or os.environ.get("YOUTUBE_API_KEY", "")
            or os.environ.get("YOUTUBE_ANALYTICS_API_KEY", "")
        ).strip()
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service

        if not self.api_key:
            raise ValueError(
                "YOUTUBE_API_KEY is not configured. Please set YOUTUBE_API_KEY in your .env file."
            )

        self._service = build("youtube", "v3", developerKey=self.api_key)
        return self._service

    def _fetch_channels_subscribers(
        self,
        channel_ids: List[str],
    ) -> Dict[str, int]:
        """Fetches subscriber counts for a batch of channels."""
        if not channel_ids:
            return {}

        svc = self._get_service()
        subs_map: Dict[str, int] = {}

        for i in range(0, len(channel_ids), 50):
            chunk = channel_ids[i:i + 50]
            logger.debug("Requesting YouTube channel statistics for %d channels: %s", len(chunk), chunk[:5])

            try:
                res = svc.channels().list(
                    part="statistics",
                    id=",".join(chunk),
                    maxResults=len(chunk),
                ).execute()

                items = res.get("items", [])
                logger.trace("Received statistics for %d channels", len(items))

                for ch in items:
                    cid = ch.get("id")
                    count = ch.get("statistics", {}).get("subscriberCount")
                    subs_map[cid] = int(count) if count is not None else 0

            except (HttpError, TimeoutError, socket.timeout) as e:
                logger.debug("Error retrieving channel subscriber data: %s", e)

        return subs_map

    def _process_video_items(
        self,
        items: List[Dict[str, Any]],
    ) -> List[VideoItem]:
        """Converts raw YouTube API items into VideoItem models with subscriber counts."""
        if not items:
            return []

        channel_ids = list({
            item.get("snippet", {}).get("channelId")
            for item in items
            if item.get("snippet", {}).get("channelId")
        })
        channel_subs = self._fetch_channels_subscribers(channel_ids)

        videos: List[VideoItem] = []

        for item in items:
            vid = item.get("id")

            if isinstance(vid, dict):
                vid = vid.get("videoId")

            snippet = item.get("snippet", {}) or {}
            statistics = item.get("statistics", {}) or {}
            content_details = item.get("contentDetails", {}) or {}

            duration_sec = parse_iso8601_duration(content_details.get("duration"))

            title = snippet.get("title", "")
            description = snippet.get("description", "")
            tags = snippet.get("tags", []) or []

            has_shorts_tag = "#shorts" in title.lower() or "#short" in title.lower() or "#shorts" in description.lower()
            is_short = (0 < duration_sec <= MAX_STANDARD_SHORT_DURATION) or (duration_sec <= MAX_EXTENDED_SHORT_DURATION and has_shorts_tag)

            thumbs = snippet.get("thumbnails", {}) or {}
            thumb_url = None

            for quality in ("maxres", "high", "medium", "default"):
                if quality in thumbs and thumbs[quality].get("url"):
                    thumb_url = thumbs[quality]["url"]
                    break

            channel_id = snippet.get("channelId")
            subs = channel_subs.get(channel_id, 0)
            views = int(statistics.get("viewCount", 0) or 0)
            likes = int(statistics.get("likeCount", 0) or 0)
            comments = int(statistics.get("commentCount", 0) or 0)

            viral_ratio = calculate_viral_ratio(views, subs, min_base=MIN_SUBSCRIBER_BASE)

            video = VideoItem(
                video_id=vid,
                title=title,
                channel_id=channel_id,
                channel_title=snippet.get("channelTitle"),
                thumbnail_url=thumb_url,
                views=views,
                likes=likes,
                comments_count=comments,
                subscribers=subs,
                duration_seconds=duration_sec,
                published_at=snippet.get("publishedAt"),
                video_url=f"https://www.youtube.com/watch?v={vid}",
                is_short=is_short,
                viral_ratio=viral_ratio,
                description=description,
                tags=tags,
            )
            videos.append(video)

        return videos

    def _enrich_and_filter_videos(
        self,
        video_ids: List[str],
        req: SearchRequest,
    ) -> List[VideoItem]:
        """Enriches video IDs with detailed statistics and channel subscriber counts."""
        svc = self._get_service()
        all_videos: List[VideoItem] = []

        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i:i + 50]
            logger.debug("Requesting YouTube video details chunk of %d videos: %s", len(chunk), chunk[:5])

            try:
                res = svc.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(chunk),
                    maxResults=len(chunk),
                ).execute()
                items = res.get("items", [])
                logger.trace("Received %d video detail items from YouTube API", len(items))

                videos = self._process_video_items(items)
                all_videos.extend(videos)

            except HttpError as e:
                logger.error("Error loading video batch details: %s", e)

        filtered: List[VideoItem] = []

        for v in all_videos:
            if req.is_shorts_only and not v.is_short:
                continue

            if req.min_views is not None and (v.views or 0) < req.min_views:
                continue

            if req.max_views is not None and (v.views or 0) > req.max_views:
                continue

            if req.max_subscribers is not None and (v.subscribers or 0) > req.max_subscribers:
                continue

            if req.min_viral_ratio is not None and v.viral_ratio < req.min_viral_ratio:
                continue

            filtered.append(v)

        filtered.sort(key=lambda x: x.viral_ratio, reverse=True)

        logger.debug("Filtered %d videos from %d raw candidates.", len(filtered), len(all_videos))
        return filtered

    def search(
        self,
        req: SearchRequest,
    ) -> List[VideoItem]:
        """
        Executes a YouTube search query with permanent SQLite cache lookup first.
        Saves 100% of API quota units when the query has been performed previously.
        """
        query_key = cache_manager.generate_query_key(req.query, req.is_shorts_only, req.region_code)
        logger.debug("Executing search request: query='%s', shorts=%s, region=%s", req.query, req.is_shorts_only, req.region_code)

        if not req.force_refresh:
            cached = cache_manager.get_cached_videos(query_key)

            if cached:
                filtered = [
                    v for v in cached
                    if (req.min_views is None or (v.views or 0) >= req.min_views)
                    and (req.max_views is None or (v.views or 0) <= req.max_views)
                    and (req.max_subscribers is None or (v.subscribers or 0) <= req.max_subscribers)
                    and (req.min_viral_ratio is None or v.viral_ratio >= req.min_viral_ratio)
                ]

                logger.info("Cache HIT for '%s': %d videos loaded from SQLite without quota usage.", req.query, len(filtered))
                return filtered

        svc = self._get_service()
        search_params: Dict[str, Any] = {
            "q": req.query,
            "part": "snippet",
            "type": "video",
            "maxResults": min(MAX_ALLOWED_RESULTS, max(1, req.max_results or DEFAULT_MAX_RESULTS)),
            "order": req.order,
            "regionCode": req.region_code or DEFAULT_REGION,
        }

        if req.is_shorts_only:
            search_params["videoDuration"] = "short"

        if req.published_after_days:
            past_date = datetime.utcnow() - timedelta(days=req.published_after_days)
            search_params["publishedAfter"] = past_date.isoformat("T") + "Z"

        try:
            logger.debug("Calling YouTube search API with parameters: %s", search_params)
            res = svc.search().list(**search_params).execute()
            video_ids = [
                item["id"]["videoId"]
                for item in items
                if "id" in item and "videoId" in item["id"]
            ]


            logger.trace("YouTube API search response received: %d items (video IDs: %s)", len(video_ids), video_ids[:5])

            if not video_ids:
                return []

            enriched = self._enrich_and_filter_videos(video_ids, req)

            if enriched:
                cache_manager.save_videos(query_key, req.query, req.is_shorts_only, enriched)

            logger.info("Cache updated for '%s': %d videos permanently stored.", req.query, len(enriched))
            return enriched

        except (TimeoutError, socket.timeout) as err:
            logger.warning("Network timeout connecting to YouTube API: %s. Falling back to cached top outliers.", err)
            fallback = cache_manager.get_top_performing_videos(limit=req.max_results)

            if fallback:
                return fallback

            raise TimeoutError("YouTube API connection timed out. Check internet connectivity.") from err

        except HttpError as e:
            logger.error("YouTube API search error: %s", e)
            raise

    def get_trending(
        self,
        req: TrendingRequest,
    ) -> List[VideoItem]:
        """Fetches trending videos for the specified region."""
        svc = self._get_service()
        params: Dict[str, Any] = {
            "chart": "mostPopular",
            "part": "snippet,statistics,contentDetails",
            "regionCode": req.region_code or DEFAULT_REGION,
            "maxResults": min(MAX_ALLOWED_RESULTS, max(1, req.max_results or DEFAULT_MAX_RESULTS)),
        }

        if req.category_id and req.category_id != "0":
            params["videoCategoryId"] = req.category_id

        try:
            logger.debug("Calling YouTube trending API with parameters: %s", params)
            res = svc.videos().list(**params).execute()
            items = res.get("items", [])

            logger.trace("YouTube trending API response received: %d raw items", len(items))

            if not items:
                return []

            raw_videos = self._process_video_items(items)

            if req.shorts_only:
                raw_videos = [
                    v for v in raw_videos
                    if v.is_short
                ]


            logger.info("Retrieved %d trending videos for region %s.", len(raw_videos), req.region_code)
            return raw_videos

        except (TimeoutError, socket.timeout) as err:
            logger.warning("Network timeout fetching trending: %s. Returning cached items.", err)
            return cache_manager.get_top_performing_videos(limit=req.max_results)

        except HttpError as e:
            logger.error("Error fetching trending videos: %s", e)
            raise

    def get_video_by_id(
        self,
        video_id: str,
    ) -> Optional[VideoItem]:
        """Fetches complete metadata for a single video by ID."""
        logger.debug("Fetching metadata for video ID: %s", video_id)

        with cache_manager._get_connection() as conn:
            row = conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()

            if row:
                tags = json.loads(row["tags_json"]) if row["tags_json"] else []

                cached_video = VideoItem(
                    video_id=row["video_id"],
                    title=row["title"],
                    channel_id=row["channel_id"],
                    channel_title=row["channel_title"],
                    thumbnail_url=row["thumbnail_url"],
                    views=row["views"],
                    likes=row["likes"],
                    comments_count=row["comments_count"],
                    subscribers=row["subscribers"],
                    duration_seconds=row["duration_seconds"],
                    published_at=row["published_at"],
                    video_url=row["video_url"],
                    is_short=bool(row["is_short"]),
                    viral_ratio=row["viral_ratio"] or 0.0,
                    description=row["description"],
                    tags=tags,
                )
                logger.trace("Resolved video ID '%s' from SQLite cache", video_id)
                return cached_video

        svc = self._get_service()

        try:
            logger.debug("Querying YouTube API for single video ID: %s", video_id)
            res = svc.videos().list(
                part="snippet,statistics,contentDetails",
                id=video_id,
            ).execute()
            items = res.get("items", [])

            logger.trace("YouTube API video detail response for %s: %d items", video_id, len(items))

            if not items:
                return None

            videos = self._process_video_items(items)
            return videos[0] if videos else None

        except (TimeoutError, socket.timeout, HttpError) as e:
            logger.error("Error fetching video details for %s: %s", video_id, e)
            return None
