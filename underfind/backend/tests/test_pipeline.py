from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from underfind.backend.core.errors import InvalidTransitionError, NotFoundError, SourceAlreadyUsedError
from underfind.backend.core.utils import parse_source_url, hamming_distance_hex
from underfind.backend.db.database import CacheManager
from underfind.backend.db.migrations import MIGRATIONS
from underfind.backend.db.pipeline_repo import PipelineRepository, check_transition
from underfind.backend.dependencies import get_pipeline_repo
from underfind.backend.main import app
from underfind.backend.schemas.pipeline import JobStatus, PageProfile, Platform, RenderTemplate, SourceVideo
from underfind.backend.schemas.video import VideoItem
from underfind.backend.services.job_service import JobService


@pytest.fixture
def repo(tmp_path: Path) -> PipelineRepository:
    return PipelineRepository(db_path=tmp_path / "pipeline.sqlite3")


@pytest.fixture
def page(repo: PipelineRepository) -> PageProfile:
    return repo.save_page(PageProfile(display_name="GTA VI Brasil", handle="@gta6br", language="pt-BR"))


def _source(source_id: str = "abcdefghijk", platform: Platform = Platform.YOUTUBE, **kwargs) -> SourceVideo:
    return SourceVideo(platform=platform, source_id=source_id, url=f"https://youtu.be/{source_id}", **kwargs)


@pytest.mark.parametrize("url, expected", [
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
    ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=3", ("youtube", "dQw4w9WgXcQ")),
    ("https://m.youtube.com/watch?feature=share&v=dQw4w9WgXcQ", ("youtube", "dQw4w9WgXcQ")),
    ("https://youtu.be/dQw4w9WgXcQ?si=x", ("youtube", "dQw4w9WgXcQ")),
    ("https://www.instagram.com/reel/C9xYz_Ab-12/?igsh=abc", ("instagram", "C9xYz_Ab-12")),
    ("https://www.instagram.com/gta6news/reel/C9xYz_Ab-12/", ("instagram", "C9xYz_Ab-12")),
    ("https://instagram.com/p/C9xYz/", ("instagram", "C9xYz")),
    ("https://www.tiktok.com/@gta6.leaks/video/7412345678901234567?lang=en", ("tiktok", "7412345678901234567")),
])
def test_parse_source_url(url: str, expected: tuple):
    assert parse_source_url(url) == expected


@pytest.mark.parametrize("url", [
    "https://vm.tiktok.com/ZMabc123/",
    "https://example.com/video/1",
    "https://www.instagram.com/gta6news/",
])
def test_parse_source_url_rejects_unresolvable(url: str):
    with pytest.raises(ValueError):
        parse_source_url(url)


def test_hamming_distance_hex():
    assert hamming_distance_hex("ff00", "ff00") == 0
    assert hamming_distance_hex("ff00", "ff01") == 1
    assert hamming_distance_hex("0000000000000000", "ffffffffffffffff") == 64


@pytest.mark.parametrize("current, target, failed_from, has_page, allowed", [
    (JobStatus.FOUND, JobStatus.DOWNLOADED, None, False, True),
    (JobStatus.FOUND, JobStatus.TRANSCRIBED, None, False, False),
    (JobStatus.TRANSCRIBED, JobStatus.TRANSLATED, None, False, False),
    (JobStatus.TRANSCRIBED, JobStatus.TRANSLATED, None, True, True),
    (JobStatus.RENDERED, JobStatus.DOWNLOADED, None, True, True),
    (JobStatus.VOICED, JobStatus.FAILED, None, True, True),
    (JobStatus.FAILED, JobStatus.VOICED, JobStatus.VOICED, True, True),
    (JobStatus.FAILED, JobStatus.RENDERED, JobStatus.VOICED, True, False),
    (JobStatus.DISCARDED, JobStatus.FOUND, None, False, True),
    (JobStatus.DISCARDED, JobStatus.DOWNLOADED, None, False, False),
    (JobStatus.EXPORTED, JobStatus.DISCARDED, None, True, False),
    (JobStatus.EXPORTED, JobStatus.FAILED, None, True, False),
    (JobStatus.EXPORTED, JobStatus.RENDERED, None, True, True),
    (JobStatus.FOUND, JobStatus.FOUND, None, False, False),
])
def test_check_transition(current, target, failed_from, has_page, allowed):
    if allowed:
        check_transition(current, target, failed_from, has_page)
    else:
        with pytest.raises(InvalidTransitionError):
            check_transition(current, target, failed_from, has_page)


def test_job_lifecycle_records_events(repo: PipelineRepository, page: PageProfile):
    repo.upsert_source(_source())
    job = repo.create_job("youtube:abcdefghijk")
    assert job.status == JobStatus.FOUND
    assert job.source.platform == Platform.YOUTUBE

    repo.transition(job.id, JobStatus.DOWNLOADED)
    repo.transition(job.id, JobStatus.TRANSCRIBED)

    with pytest.raises(InvalidTransitionError):
        repo.transition(job.id, JobStatus.TRANSLATED)

    repo.assign_page(job.id, page.id)
    repo.transition(job.id, JobStatus.TRANSLATED)

    with pytest.raises(InvalidTransitionError):
        repo.assign_page(job.id, page.id)

    failed = repo.transition(job.id, JobStatus.FAILED, error="tts timeout")
    assert failed.failed_from == JobStatus.TRANSLATED
    assert failed.error == "tts timeout"

    retried = repo.transition(job.id, JobStatus.TRANSLATED, note="retry")
    assert retried.error is None and retried.failed_from is None

    events = repo.get_job_events(job.id)
    assert [e.to_status for e in events] == [
        JobStatus.FOUND, JobStatus.DOWNLOADED, JobStatus.TRANSCRIBED,
        JobStatus.TRANSLATED, JobStatus.FAILED, JobStatus.TRANSLATED,
    ]
    assert events[4].note == "tts timeout"

    assert repo.list_jobs(status=JobStatus.TRANSLATED, page_id=page.id)[0].id == job.id
    assert repo.count_jobs_by_status() == {"translated": 1}


def test_artifacts_and_missing_entities(repo: PipelineRepository):
    repo.upsert_source(_source())
    job = repo.create_job("youtube:abcdefghijk")

    updated = repo.set_artifact(job.id, "source", "data/sources/youtube_abcdefghijk/source.mp4")
    assert updated.artifacts == {"source": "data/sources/youtube_abcdefghijk/source.mp4"}

    with pytest.raises(NotFoundError):
        repo.get_job("missing")

    with pytest.raises(NotFoundError):
        repo.create_job("youtube:unknown0000")

    with pytest.raises(NotFoundError):
        repo.create_job("youtube:abcdefghijk", page_id=999)


def test_upsert_source_keeps_known_values(repo: PipelineRepository):
    repo.upsert_source(_source(title="GTA VI trailer 3 breakdown", views=120000))
    refreshed = repo.upsert_source(_source(views=180000))

    assert refreshed.title == "GTA VI trailer 3 breakdown"
    assert refreshed.views == 180000


def test_one_job_per_source_and_page(repo: PipelineRepository, page: PageProfile):
    repo.upsert_source(_source())
    repo.create_job("youtube:abcdefghijk", page_id=page.id)

    with pytest.raises(InvalidTransitionError):
        repo.create_job("youtube:abcdefghijk", page_id=page.id)


def test_job_service_blocks_reused_sources(repo: PipelineRepository):
    service = JobService(repo, redirect_resolver=lambda url: "https://www.tiktok.com/@gta6/video/7400000000000000001")

    job = service.open_job_from_url("https://vm.tiktok.com/ZMabc123/")
    assert job.source_key == "tiktok:7400000000000000001"

    with pytest.raises(SourceAlreadyUsedError) as exc:
        service.open_job_from_url("https://www.tiktok.com/@gta6/video/7400000000000000001")
    assert exc.value.existing_job_id == job.id

    forced = service.open_job_from_url("https://www.tiktok.com/@gta6/video/7400000000000000001", force=True)
    assert forced.id != job.id


def test_job_service_blocks_cross_platform_reuploads(repo: PipelineRepository):
    service = JobService(repo)
    original = service.open_job(_source("abcdefghijk", phash="f0f0f0f0f0f0f0f0"))

    reupload = SourceVideo(
        platform=Platform.INSTAGRAM,
        source_id="C9xYz",
        url="https://www.instagram.com/reel/C9xYz/",
        phash="f0f0f0f0f0f0f0f1",
    )

    with pytest.raises(SourceAlreadyUsedError) as exc:
        service.open_job(reupload)

    assert exc.value.duplicate_of == "youtube:abcdefghijk"
    assert exc.value.existing_job_id == original.id

    different = reupload.model_copy(update={"source_id": "D1abc", "phash": "0f0f0f0f0f0f0f0f"})
    assert service.open_job(different).source_key == "instagram:D1abc"


def test_job_service_from_video_item(repo: PipelineRepository):
    video = VideoItem(video_id="dQw4w9WgXcQ", title="GTA 6 map leak", channel_title="Leaks Intl", views=900000, subscribers=12000)
    service = JobService(repo)
    job = service.open_job(service.source_from_video_item(video))

    assert job.source.title == "GTA 6 map leak"
    assert job.source.followers == 12000


def test_pages_and_templates(repo: PipelineRepository):
    template = repo.save_template(RenderTemplate(name="headline-card", layout="headline_card", card_ratio=0.4))
    assert template.id is not None and template.card_ratio == 0.4 and template.layout.value == "headline_card"

    page = repo.save_page(PageProfile(display_name="GTA 6 España", handle="@gta6es", language="es", template_id=template.id, default_hashtags=["#gta6"]))
    assert page.handle == "gta6es"
    assert page.default_hashtags == ["#gta6"]

    renamed = repo.save_page(page.model_copy(update={"display_name": "GTA VI España"}))
    assert renamed.display_name == "GTA VI España"
    assert [p.id for p in repo.list_pages()] == [page.id]

    with pytest.raises(NotFoundError):
        repo.save_page(PageProfile(display_name="x", handle="x", template_id=999))

    assert repo.delete_page(page.id) is True
    assert repo.list_pages() == []


def test_migration_upgrades_legacy_database(tmp_path: Path):
    db_path = tmp_path / "legacy.sqlite3"

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE videos (video_id TEXT PRIMARY KEY, title TEXT, viral_ratio REAL, tags_json TEXT, query_key TEXT)")
        conn.execute("CREATE TABLE ideas_board (id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT UNIQUE, status TEXT)")
        conn.execute("INSERT INTO videos VALUES ('v1', 'old', 2.0, '[]', 'BR:1:gta 6')")

    CacheManager(db_path=db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == MIGRATIONS[-1][0]
        assert conn.execute("SELECT query_key, video_id FROM query_videos").fetchall() == [("BR:1:gta 6", "v1")]
        assert "job_id" in [r[1] for r in conn.execute("PRAGMA table_info(ideas_board)")]


def test_cached_video_stays_in_every_query(tmp_path: Path):
    cache = CacheManager(db_path=tmp_path / "cache.sqlite3")
    video = VideoItem(video_id="v1", title="GTA VI Lucia gameplay", viral_ratio=12.0)

    key_a = cache.generate_query_key("gta 6", True, "US")
    key_b = cache.generate_query_key("gta vi lucia", True, "US")
    cache.save_videos(key_a, "gta 6", True, [video])
    cache.save_videos(key_b, "gta vi lucia", True, [video])

    assert [v.video_id for v in cache.get_cached_videos(key_a)] == ["v1"]
    assert [v.video_id for v in cache.get_cached_videos(key_b)] == ["v1"]


def test_jobs_api(repo: PipelineRepository):
    app.dependency_overrides[get_pipeline_repo] = lambda: repo
    client = TestClient(app)

    try:
        page_res = client.post("/api/pages", json={"display_name": "GTA VI Brasil", "handle": "gta6br", "language": "pt-BR"})
        assert page_res.status_code == 200
        page_id = page_res.json()["id"]

        assert client.post("/api/pages", json={"display_name": "dup", "handle": "gta6br"}).status_code == 409

        created = client.post("/api/jobs", json={"url": "https://www.instagram.com/reel/C9xYz/", "page_id": page_id})
        assert created.status_code == 200
        job_id = created.json()["id"]
        assert created.json()["source"]["platform"] == "instagram"

        duplicate = client.post("/api/jobs", json={"url": "https://instagram.com/reel/C9xYz/"})
        assert duplicate.status_code == 409
        assert duplicate.json()["existing_job_id"] == job_id

        assert client.post("/api/jobs", json={"url": "https://example.com/v"}).status_code == 400

        skipped = client.patch(f"/api/jobs/{job_id}/status", json={"status": "rendered"})
        assert skipped.status_code == 409

        advanced = client.patch(f"/api/jobs/{job_id}/status", json={"status": "downloaded"})
        assert advanced.json()["status"] == "downloaded"

        assert [e["to_status"] for e in client.get(f"/api/jobs/{job_id}/events").json()] == ["found", "downloaded"]
        assert client.get("/api/jobs", params={"status": "downloaded"}).json()[0]["id"] == job_id
        assert client.get("/api/jobs/stats").json() == {"downloaded": 1}
        assert client.get("/api/jobs/nope").status_code == 404

        quota = client.get("/api/quota").json()[0]
        assert quota["provider"] == "youtube" and quota["limit"] > 0
    finally:
        app.dependency_overrides.clear()
