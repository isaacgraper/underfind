from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from underfind.backend.core.errors import PermanentStageError
from underfind.backend.core.utils import hamming_distance_hex
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo, get_pipeline_runner
from underfind.backend.main import app
from underfind.backend.pipeline import download as download_module
from underfind.backend.pipeline.download import DownloadResult, YtDlpDownloader, source_updates_from_info
from underfind.backend.pipeline.media import extract_audio, extract_frame, has_audio_stream, probe_duration, run_ffmpeg
from underfind.backend.pipeline.phash import dhash
from underfind.backend.pipeline.runner import PipelineRunner
from underfind.backend.pipeline.stages import StageContext, Workspace
from underfind.backend.schemas.pipeline import (
    JobStatus,
    OnScreenText,
    Transcript,
    TranscriptSegment,
)
from underfind.backend.services.job_service import JobService


def _make_video(path: Path, pattern: str, with_audio: bool = True, seconds: int = 3) -> Path:
    args = ["-f", "lavfi", "-i", f"{pattern}=size=320x568:rate=10:duration={seconds}"]

    if with_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac", "-shortest"]

    run_ffmpeg([*args, "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(path)])
    return path


@pytest.fixture(scope="module")
def clips(tmp_path_factory) -> Dict[str, Path]:
    base = tmp_path_factory.mktemp("clips")
    return {
        "gameplay": _make_video(base / "gameplay.mp4", "testsrc"),
        "other": _make_video(base / "other.mp4", "smptebars"),
        "silent": _make_video(base / "silent.mp4", "testsrc2", with_audio=False),
    }


class FakeDownloader:
    def __init__(self, files: Dict[str, Path], errors: Optional[List[Exception]] = None):
        self.files = files
        self.errors = list(errors or [])
        self.calls = 0

    def download(self, url: str, dest_dir: Path) -> DownloadResult:
        self.calls += 1

        if self.errors:
            raise self.errors.pop(0)

        dest_dir.mkdir(parents=True, exist_ok=True)
        video = dest_dir / "source.mp4"
        shutil.copy(self.files[url], video)
        return DownloadResult(video, {"title": "GTA VI: Lucia's heist", "uploader_id": "gta6intl", "view_count": 250000, "duration": 3})


class FakeTranscriber:
    def __init__(self):
        self.calls = 0

    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> Transcript:
        self.calls += 1
        assert audio_path.exists()
        return Transcript(language="en", language_probability=0.98, model="fake", segments=[
            TranscriptSegment(start=0.0, end=2.5, text="Rockstar just confirmed the Vice City map size."),
        ])


class FakeOcr:
    def detect(self, video_path: Path, duration_seconds: float) -> List[OnScreenText]:
        return [OnScreenText(at_seconds=1.0, text="GTA 6 LEAK", confidence=0.93)]


@pytest.fixture
def repo(tmp_path: Path) -> PipelineRepository:
    return PipelineRepository(db_path=tmp_path / "pipeline.sqlite3")


def _runner(repo: PipelineRepository, tmp_path: Path, downloader, ocr=None, sleeps: Optional[list] = None) -> PipelineRunner:
    ctx = StageContext(
        repo=repo,
        workspace=Workspace(sources_dir=tmp_path / "sources", jobs_dir=tmp_path / "jobs"),
        downloader=downloader,
        transcriber=FakeTranscriber(),
        ocr=ocr,
    )
    return PipelineRunner(ctx, sleep=(sleeps.append if sleeps is not None else lambda _: None), backoff_base=1.0)


def _open(repo: PipelineRepository, url: str) -> str:
    return JobService(repo).open_job_from_url(url).id


YT_URL = "https://www.youtube.com/shorts/AAAAAAAAAAA"
IG_URL = "https://www.instagram.com/reel/C9reupload/"
TT_URL = "https://www.tiktok.com/@gta6/video/7400000000000000009"


# ------------------------------------------------------------------ media


def test_media_probe_and_extract(clips: Dict[str, Path], tmp_path: Path):
    assert probe_duration(clips["gameplay"]) == pytest.approx(3.0, abs=0.2)
    assert has_audio_stream(clips["gameplay"]) is True
    assert has_audio_stream(clips["silent"]) is False

    wav = extract_audio(clips["gameplay"], tmp_path / "a.wav")
    assert wav.stat().st_size > 10_000

    frame = extract_frame(clips["gameplay"], 1.0, tmp_path / "f.jpg")
    with Image.open(frame) as img:
        assert img.size == (320, 568)


def test_dhash_matches_rescaled_letterboxed_copy_only():
    base = Image.new("RGB", (360, 640), "white")
    draw = ImageDraw.Draw(base)
    draw.rectangle((40, 100, 200, 400), fill="red")
    draw.ellipse((150, 300, 330, 600), fill="blue")

    rescaled = base.resize((720, 1280))
    letterboxed = Image.new("RGB", (1080, 1920), "black")
    letterboxed.paste(base.resize((1080, 1920 - 400)), (0, 200))

    different = Image.new("RGB", (360, 640), "white")
    ImageDraw.Draw(different).rectangle((180, 20, 350, 250), fill="green")

    assert hamming_distance_hex(dhash(base), dhash(rescaled)) <= 2
    assert hamming_distance_hex(dhash(base), dhash(letterboxed)) <= 6
    assert hamming_distance_hex(dhash(base), dhash(different)) > 10


# --------------------------------------------------------------- download


def test_source_updates_from_info_maps_metadata():
    updates = source_updates_from_info({
        "title": "Video by gta6news",
        "description": "GTA VI trailer 3 details #gta6",
        "uploader": "GTA 6 News",
        "uploader_id": "gta6news",
        "view_count": 1200000,
        "like_count": 90000,
        "channel_follower_count": None,
        "duration": 34.6,
        "timestamp": 1758000000,
    })

    assert updates["caption"] == "GTA VI trailer 3 details #gta6"
    assert updates["author_handle"] == "gta6news"
    assert updates["duration_seconds"] == 35
    assert updates["published_at"].startswith("2025-09-16")
    assert "followers" not in updates


def test_ytdlp_login_wall_is_permanent(monkeypatch, tmp_path: Path):
    from yt_dlp.utils import DownloadError

    class WalledYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def sanitize_info(self, info):
            return info

        def extract_info(self, url, download):
            raise DownloadError("ERROR: [Instagram] C9x: Requested content is not available, rate-limit reached or login required")

    monkeypatch.setattr("yt_dlp.YoutubeDL", WalledYDL)
    downloader = YtDlpDownloader(cookies_file=None, cookies_from_browser=None, proxy=None, ffmpeg_location="ffmpeg")
    monkeypatch.setattr(downloader, "cookies_file", None)
    monkeypatch.setattr(downloader, "cookies_from_browser", None)

    with pytest.raises(PermanentStageError, match="YTDLP_COOKIES_FILE"):
        downloader.download(IG_URL, tmp_path / "dl")


def test_ytdlp_options_include_cookies_and_proxy(tmp_path: Path):
    opts = YtDlpDownloader(cookies_file="/c.txt", proxy="http://p:1", ffmpeg_location="ffmpeg")._options(tmp_path)

    assert opts["cookiefile"] == "/c.txt"
    assert opts["proxy"] == "http://p:1"
    assert opts["outtmpl"].endswith("source.%(ext)s")
    assert opts["noplaylist"] is True
    assert download_module.YTDLP_FORMAT == opts["format"]


# ----------------------------------------------------------------- runner


def test_runner_downloads_and_transcribes(repo: PipelineRepository, tmp_path: Path, clips):
    runner = _runner(repo, tmp_path, FakeDownloader({YT_URL: clips["gameplay"]}), ocr=FakeOcr())
    job_id = _open(repo, YT_URL)

    job = runner.run_until_blocked(job_id)

    assert job.status == JobStatus.TRANSCRIBED
    assert job.locked_by is None
    assert set(job.artifacts) == {"source_video", "frame", "transcript"}
    assert job.source.title == "GTA VI: Lucia's heist"
    assert job.source.views == 250000
    assert job.source.language == "en"
    assert job.source.has_onscreen_text is True
    assert job.source.phash and len(job.source.phash) == 16

    transcript = Transcript.model_validate_json(Path(job.artifacts["transcript"]).read_text())
    assert transcript.text == "Rockstar just confirmed the Vice City map size."
    assert transcript.duration_seconds == pytest.approx(3.0, abs=0.2)
    assert transcript.onscreen_text[0].text == "GTA 6 LEAK"
    assert [e.to_status for e in repo.get_job_events(job_id)] == [JobStatus.FOUND, JobStatus.DOWNLOADED, JobStatus.TRANSCRIBED]


def test_second_job_of_same_source_reuses_artifacts(repo: PipelineRepository, tmp_path: Path, clips):
    downloader = FakeDownloader({YT_URL: clips["gameplay"]})
    runner = _runner(repo, tmp_path, downloader)
    service = JobService(repo)
    first = service.open_job_from_url(YT_URL)
    runner.run_until_blocked(first.id)

    second = service.open_job_from_url(YT_URL, force=True)
    job = runner.run_until_blocked(second.id)

    assert job.status == JobStatus.TRANSCRIBED
    assert downloader.calls == 1
    assert runner.ctx.transcriber.calls == 1


def test_cross_platform_reupload_is_discarded_after_download(repo: PipelineRepository, tmp_path: Path, clips):
    runner = _runner(repo, tmp_path, FakeDownloader({
        YT_URL: clips["gameplay"],
        IG_URL: clips["gameplay"],
        TT_URL: clips["other"],
    }))
    original = _open(repo, YT_URL)
    reupload = _open(repo, IG_URL)
    unrelated = _open(repo, TT_URL)

    assert runner.run_until_blocked(original).status == JobStatus.TRANSCRIBED

    discarded = runner.run_until_blocked(reupload)
    assert discarded.status == JobStatus.DISCARDED
    assert "youtube:AAAAAAAAAAA" in repo.get_job_events(reupload)[-1].note

    assert runner.run_until_blocked(unrelated).status == JobStatus.TRANSCRIBED

    # Re-running the original must not be blocked by the discarded reupload.
    repo.transition(original, JobStatus.FOUND, note="re-run")
    assert runner.run_until_blocked(original).status == JobStatus.TRANSCRIBED


def test_silent_video_gets_empty_transcript(repo: PipelineRepository, tmp_path: Path, clips):
    runner = _runner(repo, tmp_path, FakeDownloader({YT_URL: clips["silent"]}))
    job = runner.run_until_blocked(_open(repo, YT_URL))

    assert job.status == JobStatus.TRANSCRIBED
    assert runner.ctx.transcriber.calls == 0
    assert Transcript.model_validate_json(Path(job.artifacts["transcript"]).read_text()).has_speech is False


def test_transient_errors_retry_with_backoff(repo: PipelineRepository, tmp_path: Path, clips):
    sleeps: list = []
    downloader = FakeDownloader({YT_URL: clips["gameplay"]}, errors=[ConnectionError("reset"), TimeoutError("slow")])
    runner = _runner(repo, tmp_path, downloader, sleeps=sleeps)

    job = runner.run_until_blocked(_open(repo, YT_URL))

    assert job.status == JobStatus.TRANSCRIBED
    assert downloader.calls == 3
    assert sleeps == [1.0, 2.0]


def test_exhausted_retries_fail_and_can_be_retried(repo: PipelineRepository, tmp_path: Path, clips):
    downloader = FakeDownloader({YT_URL: clips["gameplay"]}, errors=[ConnectionError("reset")] * 3)
    runner = _runner(repo, tmp_path, downloader)
    job_id = _open(repo, YT_URL)

    failed = runner.run_until_blocked(job_id)
    assert failed.status == JobStatus.FAILED
    assert failed.failed_from == JobStatus.FOUND
    assert failed.error == "ConnectionError: reset"
    assert failed.attempts == 3

    repo.transition(job_id, JobStatus.FOUND, note="retry")
    assert runner.run_until_blocked(job_id).status == JobStatus.TRANSCRIBED


def test_permanent_error_fails_without_retry(repo: PipelineRepository, tmp_path: Path, clips):
    downloader = FakeDownloader({}, errors=[PermanentStageError("Download failed: video is private")])
    runner = _runner(repo, tmp_path, downloader)

    job = runner.run_until_blocked(_open(repo, YT_URL))

    assert job.status == JobStatus.FAILED
    assert downloader.calls == 1
    assert "private" in job.error


def test_locked_job_is_skipped(repo: PipelineRepository, tmp_path: Path, clips):
    runner = _runner(repo, tmp_path, FakeDownloader({YT_URL: clips["gameplay"]}))
    job_id = _open(repo, YT_URL)
    assert repo.claim_job(job_id, "other-worker") is True

    assert runner.run_until_blocked(job_id).status == JobStatus.FOUND
    assert repo.list_runnable_job_ids([JobStatus.FOUND]) == []

    repo.release_job(job_id, "other-worker")
    assert runner.tick(max_parallel=1)[0].status == JobStatus.TRANSCRIBED


def test_run_and_transcript_api(repo: PipelineRepository, tmp_path: Path, clips):
    runner = _runner(repo, tmp_path, FakeDownloader({YT_URL: clips["gameplay"]}))
    app.dependency_overrides[get_pipeline_repo] = lambda: repo
    app.dependency_overrides[get_pipeline_runner] = lambda: runner
    client = TestClient(app)

    try:
        job_id = client.post("/api/jobs", json={"url": YT_URL}).json()["id"]
        assert client.get(f"/api/jobs/{job_id}/transcript").status_code == 404

        res = client.post(f"/api/jobs/{job_id}/run")
        assert res.status_code == 202
        assert res.json()["from_status"] == "found"

        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "transcribed"
        transcript = client.get(f"/api/jobs/{job_id}/transcript").json()
        assert transcript["language"] == "en"
        assert transcript["segments"][0]["text"].startswith("Rockstar")

        assert client.post("/api/pipeline/tick").status_code == 202
    finally:
        app.dependency_overrides.clear()
