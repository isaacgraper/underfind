# underfind/underfind/controllers/search.py
"""
Search controller that uses the YouTube Data API (via googleapiclient) to:
 - run search queries
 - fetch video details (statistics, contentDetails)
 - convert results into Video model instances
 - optionally fetch thumbnails
 - accept keyword input as list or CSV file

Environment:
 - Expects YOUTUBE_API_KEY in the environment (or pass api_key to constructor)

Notes:
 - This module is written to be synchronous and blocking. Network calls are performed
   inline; if you use this from a GUI you should call the public methods from a
   background thread to avoid freezing the UI.
 - The controller uses the LoadingOverlay component (if provided) to show/hide during network ops.
"""

from __future__ import annotations

import csv
import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Iterable, Set

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import requests
import langdetect

from underfind.models.video import Video
from underfind.ui.components.loading import LoadingOverlay

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SearchController:
    """
    Controller responsible for performing YouTube searches and returning Video models.

    Example:
        ctrl = SearchController()  # will read YOUTUBE_API_KEY from env
        videos = ctrl.search(["keto recipes", "yoga for beginners"])
    """

    DEFAULT_MAX_RESULTS = 12
    SEARCH_API_PART = "id,snippet"
    VIDEOS_API_PART = "snippet,statistics,contentDetails"

    def __init__(
        self,
        api_key: Optional[str] = None,
        loading_overlay: Optional[LoadingOverlay] = None,
        max_results: int = DEFAULT_MAX_RESULTS,
        service_kwargs: Optional[Dict[str, Any]] = None,
    ):
        """
        api_key: YouTube Data API v3 key. If None, will attempt to read YOUTUBE_API_KEY from env.
        loading_overlay: optional LoadingOverlay instance to show/hide during network ops.
        max_results: number of results per query (YouTube API max per request is 50).
        service_kwargs: extra kwargs to pass to googleapiclient.discovery.build (for testing/mocking).
        """
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        self.loading_overlay = loading_overlay
        self.max_results = max_results or self.DEFAULT_MAX_RESULTS
        self._service = None
        self._service_kwargs = service_kwargs or {}

        if not self.api_key:
            logging.warning(
                "YOUTUBE_API_KEY not provided. SearchController will not be able to perform API calls until an API key is supplied."
            )

    def _ensure_service(self):
        """Lazily create the googleapiclient service object."""
        if self._service:
            return self._service
        if not build:
            raise RuntimeError(
                "googleapiclient.discovery.build not available. Make sure google-api-python-client is installed."
            )
        if not self.api_key:
            raise RuntimeError("YouTube API key not configured (YOUTUBE_API_KEY).")
        logging.debug("Creating YouTube service client")
        self._service = build("youtube", "v3", developerKey=self.api_key, **self._service_kwargs)
        return self._service

    def search(
        self,
        keywords: Iterable[str],
        filters: Optional[Dict[str, Any]] = None,
        fetch_thumbnails: bool = False,
    ) -> List[Video]:
        """
        Run searches for a list of keyword queries and aggregate the results.

        keywords: iterable of query strings.
        filters: optional dict of filters that will be mapped to YouTube API parameters and
                 used for post-filtering. Supported keys (optional):
                   - min_views (int)
                   - max_views (int)
                   - duration_seconds_min (int)
                   - duration_seconds_max (int)
                   - max_subscribers (int)        # maximum channel subscribers
                   - months_back (int)           # published after now - months_back*30 days
                   - published_after (ISO string) # explicit publishedAfter value (overrides months_back)
                   - relevanceLanguage (str)     # passed to search.list (e.g. 'de' or 'en')
                   - language (str)              # language to check with langdetect (e.g. 'de' or 'en')
                   - order (str)                 # search order param (e.g. 'viewCount')
                   - videoDuration (str)         # 'short', 'medium', 'long'
                 Note: Some of these are passed to search.list, others are used for post-filtering.

        fetch_thumbnails: if True, will attempt to download the thumbnail bytes for each Video (blocking).

        Returns a list of Video instances (deduplicated by video_id).
        """
        if self.loading_overlay:
            try:
                self.loading_overlay.show("Buscando vídeos...")
            except Exception:
                pass

        results: List[Video] = []
        seen_ids: Set[str] = set()
        filters = filters or {}

        # Compute publishedAfter if requested
        published_after = None
        if filters.get("published_after"):
            published_after = str(filters.get("published_after"))
        elif filters.get("months_back") is not None:
            try:
                months = int(filters.get("months_back") or 0)
                delta_days = months * 30
                published_after = (datetime.utcnow() - timedelta(days=delta_days)).isoformat("T") + "Z"
            except Exception:
                published_after = None

        # pass-through search parameters
        search_params = {
            "order": filters.get("order"),
            "videoDuration": filters.get("videoDuration"),
            "relevanceLanguage": filters.get("relevanceLanguage"),
            "publishedAfter": published_after,
        }

        try:
            for i, kw in enumerate(keywords):
                kw = (kw or "").strip()
                if not kw:
                    continue
                logging.info("Searching for query [%s] (%d/%d)", kw, i + 1, sum(1 for _ in keywords))
                items = self._search_single_query(kw)
                if not items:
                    continue

                # For each batch of items (search returns minimal snippet), fetch details
                video_ids = [it["id"]["videoId"] if isinstance(it.get("id"), dict) else it.get("id") for it in items]
                video_ids = [vid for vid in video_ids if vid]
                if not video_ids:
                    continue

                details = self._fetch_videos_details(video_ids)

                # Attempt to enrich details with channel subscriber counts
                try:
                    channel_ids = [it.get("snippet", {}).get("channelId") for it in details]
                    channel_ids = [c for c in set(channel_ids) if c]
                    channel_subs_map: Dict[str, int] = {}
                    if channel_ids:
                        # chunk channel ids (API supports up to 50)
                        chunk_size = 50
                        svc = self._ensure_service()
                        for i in range(0, len(channel_ids), chunk_size):
                            chunk = channel_ids[i : i + chunk_size]
                            try:
                                req = svc.channels().list(part="statistics", id=",".join(chunk), maxResults=len(chunk))
                                resp = req.execute()
                                items = resp.get("items", []) or []
                                for ch in items:
                                    cid = ch.get("id")
                                    subs = ch.get("statistics", {}).get("subscriberCount")
                                    try:
                                        channel_subs_map[cid] = int(subs) if subs is not None else None
                                    except Exception:
                                        channel_subs_map[cid] = None
                            except HttpError:
                                # ignore channel fetch errors and proceed
                                continue
                    # attach subscriber count into each video's statistics so Video.from_youtube_api_item can pick it up
                    for it in details:
                        cid = it.get("snippet", {}).get("channelId")
                        if cid and cid in channel_subs_map:
                            stats = it.setdefault("statistics", {})
                            # only set if missing
                            if "subscriberCount" not in stats or not stats.get("subscriberCount"):
                                stats["subscriberCount"] = channel_subs_map.get(cid)
                except Exception:
                    # don't fail the whole search if channel enrichment fails
                    logging.debug("Failed to fetch channel subscriber counts", exc_info=True)

                for item in details:
                    video = Video.from_youtube_api_item(item)
                    # post-filter by provided filters (views/duration/subscribers)
                    if not self._passes_filters(video, filters):
                        continue
                    if video.video_id in seen_ids:
                        continue
                    seen_ids.add(video.video_id)
                    if fetch_thumbnails:
                        try:
                            img = video.fetch_thumbnail_image()
                            if img:
                                # store bytes to _thumbnail_bytes for the UI to use later
                                buf = getattr(img, "tobytes", None)
                                # Instead of relying on tobytes (which is raw pixel), store the downloaded bytes
                                # We perform a fresh download to keep the original bytes:
                                try:
                                    resp = requests.get(video.thumbnail_url, timeout=6)
                                    if resp.ok:
                                        video._thumbnail_bytes = resp.content
                                except Exception:
                                    pass
                        except Exception:
                            logging.debug("Failed to fetch thumbnail for %s", video.video_id, exc_info=True)
                    results.append(video)

                # small pause to avoid hitting quota too fast for many queries
                time.sleep(0.1)
        except HttpError as e:
            logging.error("YouTube API error: %s", e)
            raise
        finally:
            if self.loading_overlay:
                try:
                    self.loading_overlay.hide(destroy=True)
                except Exception:
                    pass

        return results

    def search_from_csv(
        self,
        csv_path: str,
        keyword_column: str = "keyword",
        filters: Optional[Dict[str, Any]] = None,
        fetch_thumbnails: bool = False,
    ) -> List[Video]:
        """
        Read a CSV file and run searches using the values from the provided column.

        csv_path: path to CSV file
        keyword_column: column header that contains keywords (defaults to 'keyword')
        """
        keywords = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if keyword_column not in reader.fieldnames:
                    # try common alternatives
                    alt = next((n for n in ("query", "q", "keywords", "keyword", "search") if n in (reader.fieldnames or [])), None)
                    if alt:
                        keyword_column = alt
                for row in reader:
                    val = row.get(keyword_column) or row.get("keyword") or row.get("query")
                    if val:
                        keywords.append(val.strip())
        except FileNotFoundError:
            logging.error("CSV file not found: %s", csv_path)
            raise
        except Exception as e:
            logging.exception("Error reading CSV: %s", e)
            raise

        return self.search(keywords, filters=filters, fetch_thumbnails=fetch_thumbnails)

    def _search_single_query(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Call YouTube Data API search.list for a single query.

        Supported search.list parameters accepted via `filters`:
          - order (e.g. 'viewCount')
          - videoDuration (short|medium|long)
          - relevanceLanguage (e.g. 'de' or 'en')
          - publishedAfter (ISO 8601 string, e.g. '2024-01-01T00:00:00Z')
        Returns the items list (each item is a dict with id + snippet).
        """
        svc = self._ensure_service()
        maxr = min(50, max(1, int(self.max_results)))
        try:
            params: Dict[str, Any] = {
                "q": query,
                "part": "snippet",
                "type": "video",
                "maxResults": maxr,
            }
            if filters:
                # only include params that are provided
                if filters.get("order"):
                    params["order"] = filters.get("order")
                if filters.get("videoDuration"):
                    params["videoDuration"] = filters.get("videoDuration")
                if filters.get("relevanceLanguage"):
                    params["relevanceLanguage"] = filters.get("relevanceLanguage")
                if filters.get("publishedAfter"):
                    params["publishedAfter"] = filters.get("publishedAfter")
            req = svc.search().list(**{k: v for k, v in params.items() if v is not None})
            resp = req.execute()
            items = resp.get("items", [])
            return items
        except HttpError as e:
            logging.error("search.list failed for query %s: %s", query, e)
            raise

    def _fetch_videos_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Given a list of video IDs, call videos.list to obtain snippet, statistics and contentDetails.
        """
        if not video_ids:
            return []
        svc = self._ensure_service()
        # API allows up to 50 ids per request
        out: List[Dict[str, Any]] = []
        chunk_size = 50
        for i in range(0, len(video_ids), chunk_size):
            chunk = video_ids[i : i + chunk_size]
            try:
                req = svc.videos().list(part=self.VIDEOS_API_PART, id=",".join(chunk), maxResults=len(chunk))
                resp = req.execute()
                items = resp.get("items", [])
                out.extend(items)
            except HttpError as e:
                logging.error("videos.list failed for ids %s: %s", chunk, e)
                raise
        return out

    def _passes_filters(self, video: Video, filters: Dict[str, Any]) -> bool:
        """
        Apply simple post-filters based on the video metadata.
        Supported filters:
         - min_views (int)
         - max_views (int)
         - duration_seconds_min (int)
         - duration_seconds_max (int)
         - max_subscribers (int)
         - language (str)  # if provided, langdetect will be used to check title+channel+description
        """
        if not filters:
            return True

        def to_int(v):
            try:
                return int(v) if v is not None else None
            except Exception:
                return None

        mv = to_int(filters.get("min_views"))
        if mv is not None and video.views is not None and video.views < mv:
            return False
        Mv = to_int(filters.get("max_views"))
        if Mv is not None and video.views is not None and video.views > Mv:
            return False

        dmin = to_int(filters.get("duration_seconds_min"))
        if dmin is not None and video.duration_seconds is not None and video.duration_seconds < dmin:
            return False
        dmax = to_int(filters.get("duration_seconds_max"))
        if dmax is not None and video.duration_seconds is not None and video.duration_seconds > dmax:
            return False

        max_subs = to_int(filters.get("max_subscribers") or filters.get("max_subs") or filters.get("max_subscribers"))
        if max_subs is not None and video.subscribers is not None:
            try:
                if int(video.subscribers) > max_subs:
                    return False
            except Exception:
                # if subscribers is not numeric, ignore subscriber filter
                pass

        # language detection (optional). If the caller provided a `language` filter (e.g. 'de' or 'en')
        # we attempt to detect language using langdetect on the video's title + (if available) snippet fields.
        desired_lang = filters.get("language")
        if desired_lang and langdetect:
            try:
                text = " ".join(
                    filter(
                        None,
                        [
                            getattr(video, "title", "") or "",
                            # Video model may not include description; some items may have snippet elsewhere
                        ],
                    )
                )
                if text:
                    detected = None
                    try:
                        detected = langdetect.detect(text)
                    except Exception:
                        detected = None
                    if detected and detected != desired_lang:
                        return False
            except Exception:
                # do not block results if language detection fails
                pass

        return True
