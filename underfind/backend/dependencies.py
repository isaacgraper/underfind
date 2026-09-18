from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

from underfind.backend.services.youtube_service import YouTubeService
from underfind.backend.db.database import CacheManager, cache_manager


def get_youtube_service() -> YouTubeService:
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    return YouTubeService(api_key=api_key)


def get_cache_manager() -> CacheManager:
    return cache_manager
