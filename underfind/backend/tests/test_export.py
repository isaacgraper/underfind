from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import List

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo, get_pipeline_runner
from underfind.backend.main import app
from underfind.backend.pipeline.export import FolderExporter, WebhookNotifier, compose_caption
from underfind.backend.pipeline.runner import PipelineRunner
from underfind.backend.pipeline.stages import StageContext, Workspace
from underfind.backend.pipeline.translate import TranslationDraft
from underfind.backend.schemas.pipeline import (
    Job,
    JobStatus,
    PageProfile,
    Platform,
    RenderTemplate,
    SourceVideo,
    Translation,
)
from underfind.backend.services.job_service import JobService


def _translation(**kwargs) -> Translation:
    base = dict(target_language="pt-BR", page_id=1, mode="subtitles", caption="O trailer chegou!", hashtags=["#gta6", "#gtavi"])
    return Translation(**{**base, **kwargs})


def _page(**kwargs) -> PageProfile:
    return PageProfile(**{"id": 1, "display_name": "GTA VI Brasil", "handle": "gtavibrasil", "language": "pt-BR", **kwargs})


SOURCE = SourceVideo(platform=Platform.INSTAGRAM, source_id="C9x", url="https://www.instagram.com/reel/C9x/", author_handle="gta6news", views=900000)


def test_compose_caption_with_credit_placeholders():
    page = _page(caption_footer="📸 {source_author} | {platform} {unknown}")
    assert compose_caption(_translation(), page, SOURCE) == "O trailer chegou!\n\n📸 @gta6news | instagram {unknown}\n\n#gta6 #gtavi"

    local = SourceVideo(platform=Platform.LOCAL, source_id="x", url="local://a.jpg")
    assert compose_caption(_translation(hashtags=[]), _page(caption_footer="{source_url}"), local) == "O trailer chegou!"


def _rendered_job(tmp_path: Path) -> Job:
    reel = tmp_path / "reel.mp4"
    reel.write_bytes(b"video")
    post = tmp_path / "post.jpg"
    Image.new("RGB", (10, 10)).save(post)
    slides = {}

    for i in (1, 2):
        path = tmp_path / f"carousel_{i:02d}.jpg"
        Image.new("RGB", (10, 10)).save(path)
        slides[f"carousel_{i:02d}"] = str(path)

    return Job(id="job123", source_key="instagram:C9x", source=SOURCE, status=JobStatus.RENDERED,
               artifacts={"reel": str(reel), "post": str(post), "transcript": "x", **slides})


def test_folder_export_layout_manifest_and_index(tmp_path: Path):
    exporter = FolderExporter(tmp_path / "exports")
    stamp = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
    manifest = exporter.export(_rendered_job(tmp_path), _page(), _translation(headline="GTA 6 EM *NOVEMBRO*"), 8.0, now=stamp)

    folder = Path(manifest.folder)
    assert folder == tmp_path / "exports" / "gtavibrasil" / "20260930-120000_job123"
    assert sorted(p.name for p in folder.iterdir()) == [
        "caption.txt", "carousel_01.jpg", "carousel_02.jpg", "manifest.json", "post.jpg", "reel.mp4",
    ]
    assert [(d.kind, d.files) for d in manifest.deliverables] == [
        ("reel", ["reel.mp4"]), ("post", ["post.jpg"]), ("carousel", ["carousel_01.jpg", "carousel_02.jpg"]),
    ]
    assert manifest.headline == "GTA 6 EM NOVEMBRO"
    assert manifest.source["author"] == "gta6news" and manifest.source_metrics["views"] == 900000
    assert json.loads((folder / "manifest.json").read_text())["caption"] == "O trailer chegou!\n\n#gta6 #gtavi"
    assert not list((tmp_path / "exports" / "gtavibrasil").glob(".tmp_*"))

    rows = list(csv.DictReader((tmp_path / "exports" / "exports.csv").open()))
    assert rows[0]["job_id"] == "job123" and rows[0]["deliverables"] == "reel+post+carousel"
    assert [m.job_id for m in exporter.list_exports()] == ["job123"]


def test_folder_export_cleans_up_on_missing_file(tmp_path: Path):
    job = _rendered_job(tmp_path)
    Path(job.artifacts["post"]).unlink()

    with pytest.raises(FileNotFoundError):
        FolderExporter(tmp_path / "exports").export(job, _page(), _translation())

    assert not (tmp_path / "exports" / "gtavibrasil").exists() or not any((tmp_path / "exports" / "gtavibrasil").iterdir())


def test_webhook_notifier():
    calls = []
    ok = WebhookNotifier("https://hook.test/x", post=lambda url, json, timeout: calls.append((url, json)) or SimpleNamespace(status_code=200, text=""))
    manifest = SimpleNamespace(model_dump=lambda: {"job_id": "j"})

    ok.notify(manifest)
    assert calls == [("https://hook.test/x", {"job_id": "j"})]

    WebhookNotifier("", post=lambda *a, **k: pytest.fail("no url, no call")).notify(manifest)

    failing = WebhookNotifier("https://hook.test/x", post=lambda *a, **k: SimpleNamespace(status_code=502, text="bad gateway"))
    with pytest.raises(RuntimeError, match="502"):
        failing.notify(manifest)


# ------------------------------------------------------------------ pipeline


class _Translator:
    model = "stub"

    def translate(self, req):
        return TranslationDraft(headline="", caption="Legenda", hashtags=["#gta6"])

    def shorten(self, *a):
        return []


class _FlakyNotifier:
    def __init__(self, failures: int):
        self.failures = failures
        self.sent: List[str] = []

    def notify(self, manifest):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("webhook down")

        self.sent.append(manifest.job_id)


def _setup(tmp_path: Path, notifier=None, **page_kwargs):
    repo = PipelineRepository(db_path=tmp_path / "db.sqlite3")
    template = repo.save_template(RenderTemplate(name="fast", still_seconds=2))
    page = repo.save_page(PageProfile(display_name="P", handle="pagebr", auto_approve_translation=True,
                                      template_id=template.id, outputs=["reel", "post"], **page_kwargs))
    image = tmp_path / "meme.jpg"
    img = Image.new("RGB", (1080, 1350), "white")
    ImageDraw.Draw(img).rectangle((100, 100, 900, 900), fill="navy")
    img.save(image)
    ctx = StageContext(
        repo=repo,
        workspace=Workspace(tmp_path / "sources", tmp_path / "jobs"),
        downloader=None, transcriber=None, ocr=None, translator=_Translator(),
        exporter=FolderExporter(tmp_path / "exports"),
        notifier=notifier or _FlakyNotifier(0),
    )
    runner = PipelineRunner(ctx, sleep=lambda _: None)
    job = JobService(repo).open_job_from_files([str(image)], page_id=page.id)
    return repo, runner, job


def test_render_gate_then_approval_exports(tmp_path: Path):
    repo, runner, job = _setup(tmp_path)

    job = runner.run_until_blocked(job.id)
    assert job.status == JobStatus.RENDERED and job.render_approved is False
    assert repo.list_runnable_job_ids([JobStatus.RENDERED]) == []

    app.dependency_overrides[get_pipeline_repo] = lambda: repo
    app.dependency_overrides[get_pipeline_runner] = lambda: runner
    client = TestClient(app)

    try:
        preview = client.get(f"/api/jobs/{job.id}/files/post")
        assert preview.status_code == 200 and preview.headers["content-type"] == "image/jpeg"
        assert client.get(f"/api/jobs/{job.id}/files/nope").status_code == 404

        approved = client.post(f"/api/jobs/{job.id}/render/approve").json()
        assert approved["render_approved"] is True

        client.post(f"/api/jobs/{job.id}/run")
        exported = client.get(f"/api/jobs/{job.id}").json()
        assert exported["status"] == "exported"

        folder = Path(exported["artifacts"]["export_dir"])
        assert {"reel.mp4", "post.jpg", "caption.txt", "manifest.json"} <= {p.name for p in folder.iterdir()}
        assert client.post(f"/api/jobs/{job.id}/render/approve").status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_auto_approved_render_and_webhook_retry_exports_once(tmp_path: Path):
    notifier = _FlakyNotifier(failures=1)
    repo, runner, job = _setup(tmp_path, notifier=notifier, auto_approve_render=True)

    job = runner.run_until_blocked(job.id)

    assert job.status == JobStatus.EXPORTED
    assert notifier.sent == [job.id]
    assert len(list((tmp_path / "exports" / "pagebr").iterdir())) == 1
    assert repo.get_page(job.page_id).auto_approve_render is True


def test_moving_back_clears_render_approval(tmp_path: Path):
    repo, runner, job = _setup(tmp_path)
    runner.run_until_blocked(job.id)
    repo.set_render_approved(job.id, True)

    assert repo.transition(job.id, JobStatus.VOICED, note="re-render").render_approved is False
