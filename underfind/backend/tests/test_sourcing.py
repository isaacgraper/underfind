from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import List

import pytest
from fastapi.testclient import TestClient

from underfind.backend.core import niches as niches_module
from underfind.backend.core.niches import load_niche
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.db.sourcing_repo import SourcingRepository
from underfind.backend.dependencies import get_sourcing_service
from underfind.backend.main import app
from underfind.backend.schemas.pipeline import PageProfile, Platform, SourceVideo
from underfind.backend.schemas.sourcing import CandidateStatus
from underfind.backend.schemas.video import VideoItem
from underfind.backend.services.job_service import JobService
from underfind.backend.sourcing.scanners import (
    InstagramGalleryScanner,
    InstagramGraphScanner,
    TikTokScanner,
    YouTubeKeywordScanner,
    build_scanners,
)
from underfind.backend.sourcing.scoring import score_candidate
from underfind.backend.sourcing.service import SourcingService

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)

NICHE_YAML = """
name: cars
keywords:
  include: ["porsche", "911"]
  exclude: ["crash"]
seed_pages:
  instagram: [carspage]
  tiktok: [carstok]
  youtube_channels: ["@carschannel"]
regions: [US, BR]
scan: {every_minutes: 60, max_age_days: 7, max_duration_seconds: 90, per_source_limit: 5, youtube_keyword_searches: 2}
scoring: {target_views_per_hour: 1000, target_ratio: 10, target_engagement: 0.1, min_score: 50}
auto_queue: {enabled: false, max_per_scan: 2}
"""


@pytest.fixture
def niche_dir(tmp_path: Path, monkeypatch) -> Path:
    directory = tmp_path / "niches"
    directory.mkdir()
    (directory / "cars.yaml").write_text(NICHE_YAML)
    monkeypatch.setattr(niches_module, "NICHES_DIR", directory)
    return directory


def _src(i: int, hours_ago: float = 5, views: int = 50_000, followers: int = 2_000, caption: str = "new porsche 911 reveal", duration: int = 30) -> SourceVideo:
    return SourceVideo(
        platform=Platform.INSTAGRAM, source_id=f"P{i}", url=f"https://www.instagram.com/reel/P{i}/",
        caption=caption, views=views, likes=views // 10, comments_count=views // 100, followers=followers,
        published_at=(NOW - timedelta(hours=hours_ago)).isoformat(), duration_seconds=duration,
    )


# ------------------------------------------------------------------ scoring


def test_score_strong_post_passes(niche_dir):
    niche = load_niche("cars")
    score, scores, reason = score_candidate(_src(1), niche, now=NOW)

    assert reason is None
    assert scores["velocity"] == 1.0 and scores["ratio"] == 1.0 and scores["relevance"] == 1.0
    assert scores["engagement"] == 1.0 and score == 100.0


@pytest.mark.parametrize("source, expected", [
    (_src(1, caption="porsche crash compilation"), "excluded keyword 'crash'"),
    (_src(1, hours_ago=24 * 9), "older than 7 days"),
    (_src(1, duration=300), "longer than 90s"),
    (_src(1, caption="random vlog"), "no niche keyword"),
    (_src(1, views=40, followers=500_000), "score below 50"),
])
def test_score_rejections(niche_dir, source, expected):
    _, _, reason = score_candidate(source, load_niche("cars"), now=NOW)
    assert expected in reason and reason.startswith("auto:")


def test_seed_pages_skip_relevance_and_likes_estimate_views(niche_dir):
    niche = load_niche("cars")
    no_keywords = _src(1, caption="Tá chegando o grande dia!")

    assert score_candidate(no_keywords, niche, now=NOW, seed=True)[2] is None
    assert score_candidate(no_keywords, niche, now=NOW, seed=False)[2] == "auto: no niche keyword in title or caption"

    no_views = no_keywords.model_copy(update={"views": None, "likes": 4000})
    _, scores, _ = score_candidate(no_views, niche, now=NOW, seed=True)
    assert scores["velocity"] > 0.9  # 4000 likes x 25 = 100k views estimate in 5h


# ------------------------------------------------------------------ scanners


def test_keyword_scanner_rotates_pairs(niche_dir):
    niche = load_niche("cars")
    pairs = [YouTubeKeywordScanner(None, rotation=r).pairs(niche) for r in range(3)]

    assert pairs[0] == [("porsche", "US"), ("porsche", "BR")]
    assert pairs[1] == [("911", "US"), ("911", "BR")]
    assert pairs[2] == pairs[0]


def test_keyword_scanner_builds_shorts_requests(niche_dir):
    seen = []
    service = SimpleNamespace(search=lambda req: seen.append(req) or [VideoItem(video_id="abcdefghijk", title="Porsche 911", views=10)])
    found = YouTubeKeywordScanner(service).scan(load_niche("cars"))

    assert [s.key for s in found] == ["youtube:abcdefghijk", "youtube:abcdefghijk"]
    assert seen[0].is_shorts_only and seen[0].force_refresh and seen[0].published_after_days == 7 and seen[1].region_code == "BR"


def test_channel_recent_videos_uses_uploads_playlist(tmp_path):
    from underfind.backend.core.quota import QuotaTracker
    from underfind.backend.services.youtube_service import YouTubeService

    class Req:
        def __init__(self, payload):
            self.payload = payload

        def execute(self):
            return self.payload

    calls = []
    fake = SimpleNamespace(
        channels=lambda: SimpleNamespace(list=lambda **kw: calls.append(("channels", kw)) or Req(
            {"items": [{"id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}, "statistics": {"subscriberCount": "1000"}}]})),
        playlistItems=lambda: SimpleNamespace(list=lambda **kw: calls.append(("playlist", kw)) or Req(
            {"items": [{"contentDetails": {"videoId": "abcdefghijk"}}]})),
        videos=lambda: SimpleNamespace(list=lambda **kw: calls.append(("videos", kw)) or Req(
            {"items": [{"id": "abcdefghijk", "snippet": {"title": "t", "channelId": "UC1"}, "statistics": {"viewCount": "5000"}, "contentDetails": {"duration": "PT20S"}}]})),
    )
    quota = QuotaTracker(db_path=tmp_path / "q.sqlite3", daily_limit=100)
    service = YouTubeService(api_key="k", quota=quota)
    service._service = fake

    videos = service.channel_recent_videos("@carschannel", limit=5)

    assert [v.video_id for v in videos] == ["abcdefghijk"] and videos[0].subscribers == 1000
    assert calls[0] == ("channels", {"part": "contentDetails", "forHandle": "@carschannel"})
    assert calls[1][1]["playlistId"] == "UU1"
    assert quota.status().used == 4


def test_instagram_graph_scanner_maps_business_discovery(niche_dir):
    payload = {"business_discovery": {"followers_count": 12000, "username": "carspage", "name": "Cars Page", "media": {"data": [
        {"id": "1", "caption": "Porsche 911 GT3", "permalink": "https://www.instagram.com/reel/ABC123/", "timestamp": "2026-09-29T10:00:00+0000", "like_count": 900, "comments_count": 40},
        {"id": "2", "caption": "broken", "permalink": "https://example.com/x"},
    ]}}}
    seen = {}
    get = lambda url, params, timeout: seen.update(url=url, params=params) or SimpleNamespace(status_code=200, json=lambda: payload)
    found = InstagramGraphScanner("@carspage", user_id="178", token="tok", get=get).scan(load_niche("cars"))

    assert len(found) == 1 and found[0].key == "instagram:ABC123"
    assert found[0].followers == 12000 and found[0].likes == 900 and found[0].published_at.startswith("2026-09-29T10:00")
    assert "business_discovery.username(carspage)" in seen["params"]["fields"] and seen["url"].endswith("/178")

    error = lambda *a, **k: SimpleNamespace(status_code=400, json=lambda: {"error": {"message": "Invalid token"}})
    with pytest.raises(RuntimeError, match="Invalid token"):
        InstagramGraphScanner("carspage", user_id="1", token="x", get=error).scan(load_niche("cars"))


def test_instagram_gallery_scanner_parses_dump(niche_dir):
    dump = json.dumps([
        [2, {"post_shortcode": "AAA", "username": "carspage"}],
        [3, "https://cdn/1.jpg", {"post_shortcode": "AAA", "post_url": "https://www.instagram.com/p/AAA/", "likes": 300, "description": "Porsche", "post_date": "2026-09-29 08:00:00", "username": "carspage"}],
        [3, "https://cdn/2.jpg", {"post_shortcode": "AAA", "likes": 300}],
        [3, "https://cdn/3.mp4", {"post_shortcode": "BBB", "likes": 50, "video_view_count": 4000}],
    ])
    run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, dump, "")
    found = InstagramGalleryScanner("carspage", run=run).scan(load_niche("cars"))

    assert [s.source_id for s in found] == ["AAA", "BBB"]
    assert found[0].published_at == "2026-09-29T08:00:00+00:00" and found[1].views == 4000


def test_tiktok_scanner_maps_flat_entries(niche_dir):
    info = {"entries": [
        {"id": "7400000000000000001", "url": "https://www.tiktok.com/@carstok/video/7400000000000000001", "title": "911", "view_count": 90000, "timestamp": 1790000000, "duration": 21},
        {"id": "not-a-video"},
    ]}
    seen = {}
    found = TikTokScanner("@carstok", extract=lambda url, opts: seen.update(url=url, opts=opts) or info).scan(load_niche("cars"))

    assert [s.key for s in found] == ["tiktok:7400000000000000001"]
    assert found[0].views == 90000 and found[0].duration_seconds == 21
    assert seen["url"] == "https://www.tiktok.com/@carstok" and seen["opts"]["playlistend"] == 5


def test_build_scanners(niche_dir, monkeypatch):
    niche = load_niche("cars")
    monkeypatch.delenv("IG_GRAPH_USER_ID", raising=False)

    without_key = [s.name for s in build_scanners(niche, youtube=None)]
    assert without_key == ["instagram:carspage", "tiktok:carstok"]

    monkeypatch.setenv("IG_GRAPH_USER_ID", "1")
    monkeypatch.setenv("IG_GRAPH_TOKEN", "t")
    scanners = build_scanners(niche, youtube=SimpleNamespace(api_key="k"))
    assert [s.name for s in scanners] == ["youtube_keywords", "youtube_channel:@carschannel", "instagram:carspage", "tiktok:carstok"]
    assert isinstance(scanners[2], InstagramGraphScanner)


# ------------------------------------------------------------------ service


class FakeScanner:
    def __init__(self, name: str, items: List[SourceVideo], seed: bool = True, error: Exception | None = None):
        self.name, self.items, self.seed, self.error = name, items, seed, error

    def scan(self, niche):
        if self.error:
            raise self.error
        return self.items


def _service(tmp_path: Path, scanners, clock=lambda: NOW):
    pipeline = PipelineRepository(db_path=tmp_path / "db.sqlite3")
    sourcing = SourcingRepository(pipeline.db_path, pipeline)
    return SourcingService(pipeline, sourcing, scanner_factory=lambda niche, yt, rotation: scanners, clock=clock)


def test_scan_classifies_stores_and_reports(niche_dir, tmp_path):
    used = _src(4)
    scanners = [
        FakeScanner("instagram:carspage", [_src(1), _src(2, views=100, followers=900_000), used]),
        FakeScanner("tiktok:carstok", [_src(1), _src(3, caption="porsche crash")], seed=False),
        FakeScanner("youtube_keywords", [], error=RuntimeError("quota")),
    ]
    service = _service(tmp_path, scanners)
    JobService(service.pipeline).open_job(used)

    report = service.scan("cars")

    assert (report.found, report.new, report.rejected, report.skipped) == (4, 1, 2, 1)
    assert report.errors == {"youtube_keywords": "RuntimeError: quota"}
    assert [c.source_key for c in report.top] == ["instagram:P1"]
    assert [c.source_key for c in service.sourcing.list_candidates("cars", CandidateStatus.NEW)] == ["instagram:P1"]
    assert service.sourcing.list_candidates("cars", CandidateStatus.SKIPPED)[0].reason.startswith("auto: already used by job")
    assert service.pipeline.get_source("instagram:P1").views == 50_000


def test_dry_run_saves_nothing(niche_dir, tmp_path):
    service = _service(tmp_path, [FakeScanner("s", [_src(1)])])
    report = service.scan("cars", dry_run=True)

    assert report.new == 1 and report.dry_run
    assert service.sourcing.list_candidates("cars", None) == []
    assert service.sourcing.last_scan_at("cars") is None


def test_queue_reject_and_rescan_keep_decisions(niche_dir, tmp_path):
    service = _service(tmp_path, [FakeScanner("s", [_src(1), _src(2), _src(3)])])
    br = service.pipeline.save_page(PageProfile(display_name="BR", handle="carsbr", niche="cars"))
    es = service.pipeline.save_page(PageProfile(display_name="ES", handle="carses", niche="cars"))
    service.pipeline.save_page(PageProfile(display_name="Other", handle="other", niche=None))
    service.scan("cars")
    first, second, third = service.sourcing.list_candidates("cars", CandidateStatus.NEW)

    queued = service.queue(first.id)
    assert queued.status == CandidateStatus.QUEUED and len(queued.job_ids) == 2
    assert {service.pipeline.get_job(j).page_id for j in queued.job_ids} == {br.id, es.id}

    service.reject(second.id)
    service.scan("cars")

    assert service.sourcing.get_candidate(first.id).status == CandidateStatus.QUEUED
    assert service.sourcing.get_candidate(second.id).status == CandidateStatus.REJECTED
    assert service.sourcing.get_candidate(third.id).status == CandidateStatus.NEW

    for page_id in (br.id, es.id):
        service.pipeline.save_page(service.pipeline.get_page(page_id).model_copy(update={"active": False}))

    with pytest.raises(ValueError, match="No active page"):
        service.queue(third.id)


def test_auto_queue_and_scheduling(niche_dir, tmp_path):
    (niche_dir / "cars.yaml").write_text(NICHE_YAML.replace("enabled: false", "enabled: true"))
    clock = {"now": NOW}
    service = _service(tmp_path, [FakeScanner("s", [_src(1), _src(2), _src(3)])], clock=lambda: clock["now"])
    service.pipeline.save_page(PageProfile(display_name="BR", handle="carsbr", niche="cars"))

    reports = service.run_due_scans()
    assert len(reports) == 1 and reports[0].queued == 2
    assert len(service.sourcing.list_candidates("cars", CandidateStatus.QUEUED)) == 2

    clock["now"] = NOW + timedelta(minutes=30)
    assert service.run_due_scans() == []

    clock["now"] = NOW + timedelta(minutes=61)
    assert len(service.run_due_scans()) == 1


def test_scheduled_scans_can_be_disabled(niche_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCING_ENABLED", "false")
    assert _service(tmp_path, [FakeScanner("s", [_src(1)])]).run_due_scans() == []


def test_ingest_and_api(niche_dir, tmp_path):
    service = _service(tmp_path, [FakeScanner("s", [_src(1)])])
    page = service.pipeline.save_page(PageProfile(display_name="BR", handle="carsbr", niche="cars"))
    app.dependency_overrides[get_sourcing_service] = lambda: service
    client = TestClient(app)

    try:
        report = client.post("/api/scan/cars").json()
        assert report["new"] == 1 and report["top"][0]["source"]["url"].endswith("/P1/")
        assert client.post("/api/scan/nope").status_code == 404

        ingested = client.post("/api/candidates", json={
            "url": "https://www.tiktok.com/@x/video/7400000000000000099", "niche": "cars", "caption": "vidIQ outlier",
            "views": 200000, "likes": 20000, "followers": 5000, "published_at": (NOW - timedelta(hours=3)).isoformat(),
        }).json()
        assert ingested["status"] == "new" and ingested["scanner"] == "external"

        listed = client.get("/api/candidates", params={"niche": "cars"}).json()
        assert {c["source_key"] for c in listed} == {"instagram:P1", "tiktok:7400000000000000099"}
        assert listed == sorted(listed, key=lambda c: c["score"], reverse=True)

        queued = client.post(f"/api/candidates/{ingested['id']}/queue", json={"page_ids": [page.id], "mode": "dub"}).json()
        assert queued["status"] == "queued"
        assert service.pipeline.get_job(queued["job_ids"][0]).mode == "dub"

        instagram = next(c for c in listed if c["source_key"] == "instagram:P1")
        rejected = client.post(f"/api/candidates/{instagram['id']}/reject", json={"reason": "not our style"}).json()
        assert rejected["status"] == "rejected" and rejected["reason"] == "not our style"
        assert client.get("/api/scans").json()[0]["niche"] == "cars"
    finally:
        app.dependency_overrides.clear()
