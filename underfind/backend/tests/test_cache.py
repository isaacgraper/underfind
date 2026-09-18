from __future__ import annotations

import pytest
from pathlib import Path

from underfind.backend.core.cache import CacheManager
from underfind.backend.core.models import VideoItem


@pytest.fixture
def cache_mgr(tmp_path: Path) -> CacheManager:
    test_db = tmp_path / "test_cache.sqlite3"
    return CacheManager(db_path=test_db)


def test_cache_save_and_retrieve_videos(cache_mgr: CacheManager):
    query_key = cache_mgr.generate_query_key("finance", True, "BR")
    videos = [
        VideoItem(
            video_id="v1",
            title="Outlier Video 1",
            views=100000,
            subscribers=2000,
            viral_ratio=50.0,
            video_url="https://youtube.com/shorts/v1",
            is_short=True,
        ),
        VideoItem(
            video_id="v2",
            title="Outlier Video 2",
            views=50000,
            subscribers=5000,
            viral_ratio=10.0,
            video_url="https://youtube.com/shorts/v2",
            is_short=True,
        ),
    ]

    cache_mgr.save_videos(query_key, "finance", True, videos)
    cached = cache_mgr.get_cached_videos(query_key)

    assert cached is not None
    assert len(cached) == 2
    # Should be sorted by viral ratio descending
    assert cached[0].video_id == "v1"
    assert cached[0].viral_ratio == 50.0
    assert cached[1].video_id == "v2"


def test_cache_ideas_board_crud(cache_mgr: CacheManager):
    video = VideoItem(
        video_id="idea1",
        title="Psychology of Scrolling",
        channel_title="Creator Lab",
        views=300000,
        subscribers=5000,
        viral_ratio=60.0,
        duration_seconds=45,
        video_url="https://youtube.com/shorts/idea1",
    )

    # 1. Create / Save Idea
    saved = cache_mgr.save_idea(
        video=video,
        status="backlog",
        hook_text="Stop doing this in the first 3 seconds",
        notes="Model visual pattern interrupt",
    )
    assert saved["video_id"] == "idea1"
    assert saved["status"] == "backlog"

    # 2. Read Ideas
    all_ideas = cache_mgr.get_all_ideas()
    assert len(all_ideas) == 1
    assert all_ideas[0]["video_id"] == "idea1"

    # 3. Update Status
    updated = cache_mgr.update_idea_status("idea1", "in_progress", notes="Drafting script")
    assert updated is True

    ideas_after_update = cache_mgr.get_all_ideas()
    assert ideas_after_update[0]["status"] == "in_progress"
    assert ideas_after_update[0]["script_notes"] == "Drafting script"

    # 4. Delete Idea
    deleted = cache_mgr.delete_idea("idea1")
    assert deleted is True
    assert len(cache_mgr.get_all_ideas()) == 0
