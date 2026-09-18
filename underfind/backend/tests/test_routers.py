from __future__ import annotations

from fastapi.testclient import TestClient
from underfind.backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "underfind-api"
    assert "youtube_api_configured" in data


def test_dashboard_stats_endpoint():
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "cached_videos_count" in data
    assert "max_viral_ratio" in data
    assert "ideas_total" in data


def test_ideas_crud_lifecycle():
    idea_payload = {
        "video": {
            "video_id": "test_vid_123",
            "title": "Test Title For Router",
            "channel_title": "Test Channel",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "views": 50000,
            "subscribers": 1000,
            "viral_ratio": 50.0,
            "duration_seconds": 45,
            "video_url": "https://youtube.com/shorts/test_vid_123",
            "is_short": True,
        },
        "status": "backlog",
        "hook_text": "Sample Hook",
        "notes": "Testing router",
    }

    res_post = client.post("/api/ideas", json=idea_payload)
    assert res_post.status_code == 200
    assert res_post.json()["video_id"] == "test_vid_123"

    res_patch = client.patch("/api/ideas/test_vid_123", json={"status": "in_progress", "notes": "Updated"})
    assert res_patch.status_code == 200
    assert res_patch.json()["new_status"] == "in_progress"

    res_delete = client.delete("/api/ideas/test_vid_123")
    assert res_delete.status_code == 200
    assert res_delete.json()["status"] == "deleted"
