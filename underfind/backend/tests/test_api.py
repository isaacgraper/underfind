from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from underfind.backend.api.app import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "underfind-api"
    assert data["version"] == "2.1.0"
    assert "youtube_api_configured" in data


def test_dashboard_stats_endpoint():
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "cached_videos_count" in data
    assert "max_viral_ratio" in data
    assert "ideas_total" in data
    assert "ideas_backlog" in data
    assert "ideas_in_progress" in data
    assert "ideas_done" in data
    assert "top_outliers" in data
    assert "recent_ideas" in data


def test_ideas_board_endpoints():
    test_video = {
        "video_id": "test_api_video_1",
        "title": "API Test Outlier Video",
        "channel_title": "Test Channel",
        "thumbnail_url": "https://example.com/thumb.jpg",
        "views": 250000,
        "subscribers": 5000,
        "viral_ratio": 50.0,
        "duration_seconds": 40,
        "video_url": "https://youtube.com/shorts/test_api_video_1",
        "is_short": True,
    }

    # 1. Save Idea
    create_res = client.post(
        "/api/ideas",
        json={
            "video": test_video,
            "status": "backlog",
            "hook_text": "This is a tested hook.",
            "notes": "Testing notes.",
        },
    )
    assert create_res.status_code == 200
    saved = create_res.json()
    assert saved["video_id"] == "test_api_video_1"
    assert saved["status"] == "backlog"

    # 2. List Ideas
    list_res = client.get("/api/ideas")
    assert list_res.status_code == 200
    ideas = list_res.json()
    assert any(i["video_id"] == "test_api_video_1" for i in ideas)

    # 3. Update Status
    patch_res = client.patch(
        "/api/ideas/test_api_video_1",
        json={"status": "in_progress", "notes": "Updated notes"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["new_status"] == "in_progress"

    # 4. Delete Idea
    del_res = client.delete("/api/ideas/test_api_video_1")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"
