"""
Self-contained backend for the Playwright suite: the real API, worker, renderer (ffmpeg) and exporter on a
throwaway data directory, with the network-bound parts (download, Whisper, translation, OCR, scanners) replaced
by deterministic fakes. Usage: python -m underfind.backend.e2e.server  (E2E_DIR, PORT).
"""
from __future__ import annotations

import os
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

E2E_DIR = Path(os.environ.get("E2E_DIR", "/tmp/underfind-e2e")).resolve()
PORT = int(os.environ.get("PORT", "8765"))

if E2E_DIR.exists():
    shutil.rmtree(E2E_DIR)

E2E_DIR.mkdir(parents=True)
os.environ["EXPORT_DIR"] = str(E2E_DIR / "exports")
os.environ["PIPELINE_WORKER_ENABLED"] = "true"
os.environ["WORKER_POLL_INTERVAL_SECONDS"] = "0.5"
os.environ["AI_MODE"] = "local"

import uvicorn  # noqa: E402

from underfind.backend.core import niches as niches_module  # noqa: E402
from underfind.backend.db.pipeline_repo import PipelineRepository  # noqa: E402
from underfind.backend.db.sourcing_repo import SourcingRepository  # noqa: E402
from underfind.backend.dependencies import get_pipeline_repo, get_pipeline_runner, get_sourcing_service  # noqa: E402
from underfind.backend.pipeline import runner as runner_module  # noqa: E402
from underfind.backend.pipeline.download import DownloadResult  # noqa: E402
from underfind.backend.pipeline.media import run_ffmpeg  # noqa: E402
from underfind.backend.pipeline.runner import PipelineRunner  # noqa: E402
from underfind.backend.pipeline.stages import StageContext, Workspace  # noqa: E402
from underfind.backend.pipeline.translate import TranslationDraft  # noqa: E402
from underfind.backend.schemas.pipeline import OnScreenText, PageProfile, Platform, SourceVideo, Transcript, TranscriptSegment  # noqa: E402
from underfind.backend.sourcing import service as sourcing_module  # noqa: E402
from underfind.backend.sourcing.service import SourcingService  # noqa: E402

NICHE_YAML = """
name: gta6
description: GTA VI de teste
keywords:
  include: ["gta 6"]
  exclude: []
seed_pages:
  instagram: [gta6news]
regions: [US]
hashtags: ["#gta6"]
glossary: ["GTA VI", "Rockstar"]
scan: {every_minutes: 0, max_age_days: 7, max_duration_seconds: 120, per_source_limit: 5, youtube_keyword_searches: 0}
scoring: {target_views_per_hour: 1000, target_ratio: 10, target_engagement: 0.1, min_score: 10}
auto_queue: {enabled: false, max_per_scan: 2}
"""

niche_dir = E2E_DIR / "niches"
niche_dir.mkdir()
(niche_dir / "gta6.yaml").write_text(NICHE_YAML)
niches_module.NICHES_DIR = niche_dir

# Visually distinct clips so the perceptual-hash dedup does not merge different test posts.
clips: List[Path] = []

for n, pattern in enumerate(["testsrc", "testsrc2", "smptebars", "smptehdbars", "rgbtestsrc", "yuvtestsrc"]):
    path = E2E_DIR / f"clip{n}.mp4"
    run_ffmpeg([
        "-f", "lavfi", "-i", f"{pattern}=size=320x568:rate=10:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:a", "aac", "-shortest",
        "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(path),
    ])
    clips.append(path)


class FakeDownloader:
    assigned: dict = {}
    lock = threading.Lock()

    def download(self, url: str, dest_dir: Path) -> DownloadResult:
        with FakeDownloader.lock:
            index = FakeDownloader.assigned.setdefault(url, len(FakeDownloader.assigned) % len(clips))

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(clips[index], dest_dir / "source.mp4")
        return DownloadResult(dest_dir / "source.mp4", {"title": "GTA VI leak", "uploader_id": "gta6intl", "view_count": 250000, "duration": 3})


class FakeTranscriber:
    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> Transcript:
        return Transcript(language="en", language_probability=0.99, model="fake", segments=[
            TranscriptSegment(start=0.0, end=2.5, text="Rockstar just confirmed the Vice City map size."),
        ])


class FakeOcr:
    def available(self) -> bool:
        return True

    def read_image(self, path: Path, media_file: Optional[str] = None) -> List[OnScreenText]:
        return [
            OnScreenText(at_seconds=0, text="ROCKSTAR CONFIRMS", confidence=0.95, box=[10, 20, 310, 90], media_file=media_file),
            OnScreenText(at_seconds=0, text="THE VICE CITY MAP", confidence=0.95, box=[10, 92, 310, 162], media_file=media_file),
        ]

    def read_images(self, paths: List[Path]) -> Optional[List[OnScreenText]]:
        return []

    def detect(self, video_path: Path, duration_seconds: float) -> List[OnScreenText]:
        return []


class FakeTranslator:
    model = "fake-translator"

    def translate(self, req) -> TranslationDraft:
        return TranslationDraft.model_validate({
            "segments": [{"index": s.index, "text": "A Rockstar confirmou o tamanho do mapa."} for s in req.segments],
            "headline": "ROCKSTAR CONFIRMA O MAPA DE VICE CITY",
            "caption": "O mapa de Vice City foi confirmado. O que você achou?",
            "hashtags": ["gta6", "#mapa"],
            "onscreen_text": [],
        })

    def shorten(self, target_language, segments, glossary):
        return []


class FakeScanner:
    name = "fake"
    seed = True
    batch = 0
    lock = threading.Lock()

    def scan(self, niche) -> List[SourceVideo]:
        with FakeScanner.lock:
            FakeScanner.batch += 1
            batch = FakeScanner.batch

        now = datetime.now(timezone.utc)
        return [
            SourceVideo(
                platform=Platform.INSTAGRAM, source_id=f"E2E{batch}x{i}", url=f"https://www.instagram.com/reel/E2E{batch}x{i}/",
                title=f"Leak {batch}.{i}: mapa de Vice City", caption="gta 6 map", author_handle="gta6news", views=90_000 - i * 1000,
                likes=9_000, comments_count=900, followers=2_000, duration_seconds=3, published_at=(now - timedelta(hours=4)).isoformat(),
            )
            for i in range(1, 4)
        ]


repo = PipelineRepository(db_path=E2E_DIR / "pipeline.sqlite3")
sourcing = SourcingService(
    repo, SourcingRepository(repo.db_path, repo), scanner_factory=lambda niche, youtube, rotation: [FakeScanner()],
)
runner = PipelineRunner(
    StageContext(
        repo=repo,
        workspace=Workspace(sources_dir=E2E_DIR / "sources", jobs_dir=E2E_DIR / "jobs"),
        downloader=FakeDownloader(),
        transcriber=FakeTranscriber(),
        ocr=FakeOcr(),
        translator=FakeTranslator(),
        ai_mode="local",
    ),
    backoff_base=0.1,
)

runner_module.get_default_runner = lambda: runner
sourcing_module.get_sourcing_service = lambda: sourcing

from underfind.backend.main import app  # noqa: E402

app.dependency_overrides[get_pipeline_repo] = lambda: repo
app.dependency_overrides[get_pipeline_runner] = lambda: runner
app.dependency_overrides[get_sourcing_service] = lambda: sourcing

repo.save_page(PageProfile(
    display_name="GTA VI Brasil", handle="gta6brasil", language="pt-BR", niche="gta6", brand_tag="GTA VI BRASIL", outputs=["reel"],
))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
