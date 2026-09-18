from __future__ import annotations

import pytest
from underfind.backend.core.models import VideoItem, SearchRequest, IdeaItem
from underfind.backend.core.utils import calculate_viral_ratio


def test_calculate_viral_ratio_standard():
    # 50,000 views / 5,000 subscribers = 10.0x
    ratio = calculate_viral_ratio(50000, 5000)
    assert ratio == 10.0


def test_calculate_viral_ratio_small_channel_baseline():
    # When channel has less than 100 subs (e.g. 10), baseline of 100 is used
    # 10,000 views / 100 baseline = 100.0x
    ratio = calculate_viral_ratio(10000, 10)
    assert ratio == 100.0


def test_calculate_viral_ratio_zero_views():
    ratio = calculate_viral_ratio(0, 1000)
    assert ratio == 0.0

    ratio_none = calculate_viral_ratio(None, 1000)
    assert ratio_none == 0.0


def test_search_request_defaults():
    req = SearchRequest(query="productivity")
    assert req.query == "productivity"
    assert req.is_shorts_only is False
    assert req.max_results == 25
    assert req.region_code == "BR"
    assert req.force_refresh is False


def test_idea_item_model():
    idea = IdeaItem(
        video_id="abc123xyz",
        title="Stop Scrolling Test",
        channel_title="Growth Lab",
        views=150000,
        subscribers=3000,
        viral_ratio=50.0,
        duration_seconds=45,
        video_url="https://youtube.com/shorts/abc123xyz",
        status="backlog",
        hook_text="This is an opening hook",
    )
    assert idea.video_id == "abc123xyz"
    assert idea.status == "backlog"
    assert idea.viral_ratio == 50.0
