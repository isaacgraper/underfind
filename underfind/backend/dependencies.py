from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

from underfind.backend.services.youtube_service import YouTubeService
from underfind.backend.db.database import CacheManager, cache_manager
from underfind.backend.db.pipeline_repo import PipelineRepository, pipeline_repo
from underfind.backend.core.quota import QuotaTracker, youtube_quota


def get_youtube_service() -> YouTubeService:
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    return YouTubeService(api_key=api_key)


def get_cache_manager() -> CacheManager:
    return cache_manager


def get_pipeline_repo() -> PipelineRepository:
    return pipeline_repo


def get_youtube_quota() -> QuotaTracker:
    return youtube_quota


def get_pipeline_runner():
    from underfind.backend.pipeline.runner import get_default_runner
    return get_default_runner()
