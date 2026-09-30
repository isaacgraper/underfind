from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from underfind.backend.core.errors import PermanentStageError
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo
from underfind.backend.main import app
from underfind.backend.pipeline.download import (
    DownloadResult,
    GalleryDlDownloader,
    MediaDownloader,
    NoVideoInPost,
    _gallery_info,
)
from underfind.backend.pipeline.headline import auto_highlight, clean_ocr_text, detect_headline
from underfind.backend.pipeline.local_translate import LocalTranslator
from underfind.backend.pipeline.media import probe_duration
from underfind.backend.pipeline.runner import PipelineRunner
from underfind.backend.pipeline.stages import StageContext, Workspace, load_media
from underfind.backend.pipeline.translate import SegmentInput, TranslationDraft, TranslationInput
from underfind.backend.schemas.pipeline import (
    JobStatus,
    MediaType,
    OnScreenText,
    PageProfile,
    Platform,
    RenderTemplate,
    Transcript,
    Translation,
)
from underfind.backend.services.job_service import JobService


def _line(text: str, box: List[int], media_file: str = "media_00.jpg") -> OnScreenText:
    return OnScreenText(at_seconds=0, text=text, confidence=0.95, box=box, media_file=media_file)


# The reference post (1170x1465): brand tag + 4 headline lines in the bottom band.
REFERENCE_LINES = [
    _line("GRANDTHEFTAUT06", [421, 961, 752, 998]),
    _line("IF YOUR CHILD IS BORN", [88, 1010, 1078, 1116]),
    _line("ONN0VEMBER192026", [67, 1117, 1086, 1220]),
    _line("YOU GET A FREE COPY", [97, 1225, 1076, 1330]),
    _line("OF GTA 6", [385, 1332, 790, 1437]),
]


# ---------------------------------------------------------------- headline


def test_detect_headline_on_reference_post():
    headline = detect_headline(REFERENCE_LINES, 1170, 1465, brand_hints=["grandtheftauto6"], media_file="media_00.jpg")

    assert headline.text == "IF YOUR CHILD IS BORN\nONNOVEMBER 192026\nYOU GET A FREE COPY\nOF GTA 6"
    assert headline.brand_text == "GRANDTHEFTAUT06"
    assert headline.region == [67, 961, 1086, 1437]
    assert headline.position == "bottom"


def test_detect_headline_ignores_small_labels_and_finds_top_band():
    labels = [_line("$2 BILLION", [600, 400, 760, 430]), _line("$5 MILLION", [40, 1200, 180, 1230])]
    assert detect_headline(labels, 1080, 1350) is None

    top = [_line("WAIT FOR THE", [60, 60, 1020, 170]), _line("LAST ONE", [300, 180, 780, 290])]
    headline = detect_headline(top, 1080, 1350)
    assert headline.position == "top" and headline.text == "WAIT FOR THE\nLAST ONE"


def test_detect_headline_same_line_boxes_join_left_to_right():
    lines = [_line("VICE", [500, 900, 700, 1000]), _line("WELCOME TO", [60, 900, 480, 1000]), _line("CITY 2026", [720, 900, 1020, 1000])]
    assert detect_headline(lines, 1080, 1350).text == "WELCOME TO VICE CITY 2026"


def test_clean_ocr_text():
    assert clean_ocr_text("ONN0VEMBER192026") == "ONNOVEMBER 192026"
    assert clean_ocr_text("GTA6 IN 2026") == "GTA 6 IN 2026"
    assert clean_ocr_text("R$10") == "R$10"


@pytest.mark.parametrize("text, expected", [
    ("IF YOUR CHILD IS BORN ON NOVEMBER 19 2026, YOU GET A FREE COPY OF GTA 6",
     "IF YOUR CHILD IS BORN ON *NOVEMBER 19 2026*, YOU GET A FREE COPY OF GTA 6"),
    ("SE SEU FILHO NASCER EM 19 DE NOVEMBRO DE 2026, VOCÊ GANHA GTA 6",
     "SE SEU FILHO NASCER EM *19 DE NOVEMBRO DE 2026*, VOCÊ GANHA GTA 6"),
    ("GTA 6 CUSTOU US$ 2 BILHÕES", "GTA 6 CUSTOU *US$ 2 BILHÕES*"),
    ("85% DOS JOGADORES", "*85%* DOS JOGADORES"),
    ("SEM NÚMEROS AQUI", "SEM NÚMEROS AQUI"),
    ("JÁ MARCADO *AQUI*", "JÁ MARCADO *AQUI*"),
    ("2026", "2026"),
])
def test_auto_highlight(text, expected):
    assert auto_highlight(text) == expected


# ---------------------------------------------------------------- downloads


def test_gallery_downloader_names_files_and_reads_metadata(tmp_path: Path):
    seen: List[List[str]] = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        dest = Path(cmd[cmd.index("-D") + 1])
        (dest / "media_01.jpg").write_bytes(b"a")
        (dest / "media_02.mp4").write_bytes(b"b")
        (dest / "media_01.jpg.json").write_text(json.dumps({"description": "GTA 6 👀", "username": "gta6news", "likes": 5000, "post_date": "2026-06-13 15:00:00"}))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    downloader = GalleryDlDownloader(cookies_file="/c.txt", run=fake_run)
    result = downloader.download("https://www.instagram.com/p/ABC/", tmp_path)

    assert [p.name for p in result.media_files] == ["media_01.jpg", "media_02.mp4"]
    assert result.info["uploader_id"] == "gta6news" and result.info["like_count"] == 5000
    assert result.info["timestamp"] > 0
    assert "-C" in seen[0] and "--write-metadata" in seen[0]


def test_gallery_downloader_login_wall_is_permanent(tmp_path: Path):
    fake_run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "[instagram][error] HttpError: 401 login required")

    with pytest.raises(PermanentStageError, match="YTDLP_COOKIES_FILE"):
        GalleryDlDownloader(run=fake_run).download("https://www.instagram.com/p/ABC/", tmp_path)


def test_gallery_info_tiktok_author():
    info = _gallery_info({"desc": "x", "author": {"uniqueId": "gta6.tt", "nickname": "GTA TT"}})
    assert info["uploader_id"] == "gta6.tt" and info["uploader"] == "GTA TT"


class _Recorder:
    def __init__(self, name: str, fail: Optional[Exception] = None):
        self.name, self.fail, self.calls = name, fail, []

    def download(self, url, dest):
        self.calls.append(url)

        if self.fail:
            raise self.fail

        return DownloadResult(None, {"by": self.name})


def test_media_downloader_routing(tmp_path: Path):
    video, gallery = _Recorder("video"), _Recorder("gallery")
    downloader = MediaDownloader(video=video, gallery=gallery)

    assert downloader.download("https://www.instagram.com/p/ABC/", tmp_path).info["by"] == "gallery"
    assert downloader.download("https://www.instagram.com/reel/ABC/", tmp_path).info["by"] == "video"

    no_video = MediaDownloader(video=_Recorder("video", NoVideoInPost("There is no video in this post")), gallery=gallery)
    assert no_video.download("https://www.tiktok.com/@a/video/1", tmp_path).info["by"] == "gallery"


# ------------------------------------------------------------ pipeline with images


def _image(path: Path, color: str, headline: bool = False) -> Path:
    img = Image.new("RGB", (1080, 1350), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle((100, 150, 700, 800), fill="white")
    draw.ellipse((500, 500, 1000, 1000), fill="black")

    if headline:
        draw.rectangle((0, 1000, 1080, 1350), fill="black")

    img.save(path)
    return path


class FakeImageOcr:
    """read_image returns the reference headline scaled onto the fake 1080x1350 cover."""

    def available(self) -> bool:
        return True

    def read_image(self, path: Path, at_seconds: float = 0.0, media_file: Optional[str] = None) -> List[OnScreenText]:
        if not (media_file or "").startswith("media_00"):
            return [_line("2013", [100, 60, 300, 140], media_file)]

        return [
            _line("GTA6BR", [420, 1010, 660, 1040], media_file),
            _line("GTA 6 IS COMING ON", [60, 1060, 1020, 1150], media_file),
            _line("NOVEMBER 19 2026", [80, 1160, 1000, 1250], media_file),
        ]

    def read_images(self, paths: List[Path]) -> List[OnScreenText]:
        return [line for p in paths for line in self.read_image(p, media_file=p.name)]

    def detect(self, video_path, duration):
        return []


class HeadlineTranslator:
    model = "fake"

    def __init__(self):
        self.requests: List[TranslationInput] = []

    def translate(self, req: TranslationInput) -> TranslationDraft:
        self.requests.append(req)
        return TranslationDraft(headline="GTA 6 CHEGA EM 19 DE NOVEMBRO DE 2026", caption="Chegando!", hashtags=["#gta6"],
                                onscreen_text=[{"source": t, "text": t} for t in req.onscreen_text])

    def shorten(self, *args):
        return []


@pytest.fixture
def repo(tmp_path: Path) -> PipelineRepository:
    return PipelineRepository(db_path=tmp_path / "pipeline.sqlite3")


def _ctx(repo: PipelineRepository, tmp_path: Path, translator=None) -> StageContext:
    return StageContext(
        repo=repo,
        workspace=Workspace(sources_dir=tmp_path / "sources", jobs_dir=tmp_path / "jobs"),
        downloader=None,
        transcriber=SimpleNamespace(transcribe=lambda *a, **k: pytest.fail("images must not be transcribed")),
        ocr=FakeImageOcr(),
        translator=translator or HeadlineTranslator(),
    )


def test_carousel_from_local_files_to_translated_headline(repo: PipelineRepository, tmp_path: Path):
    cover = _image(tmp_path / "cover.png", "purple", headline=True)
    second = _image(tmp_path / "second.jpg", "orange")
    template = repo.save_template(RenderTemplate(name="fast", still_seconds=2))
    page = repo.save_page(PageProfile(
        display_name="GTA VI BR", handle="gta6br", niche="gta6", auto_approve_translation=True,
        template_id=template.id, outputs=["reel", "post", "carousel"],
    ))
    translator = HeadlineTranslator()
    runner = PipelineRunner(_ctx(repo, tmp_path, translator), sleep=lambda _: None)

    job = JobService(repo).open_job_from_files(
        [str(cover), str(second)], source_url="https://www.instagram.com/p/XYZ/", caption="GTA 6 is coming", author_handle="gta6br", page_id=page.id,
    )
    assert job.source.platform == Platform.LOCAL

    job = runner.run_until_blocked(job.id)
    assert job.status == JobStatus.RENDERED
    assert probe_duration(Path(job.artifacts["reel"])) == pytest.approx(4.0, abs=0.2)
    assert {"post", "carousel_01", "carousel_02"} <= set(job.artifacts)

    with Image.open(job.artifacts["post"]) as post:
        assert post.size == (1080, 1350)

    source = repo.get_source(job.source_key)
    assert source.media_type == MediaType.CAROUSEL
    assert source.media_files == ["media_00.png", "media_01.jpg"]

    media_type, files = load_media(tmp_path / "sources" / job.source_key.replace(":", "_"))
    assert media_type == MediaType.CAROUSEL and all(f.exists() for f in files)

    transcript = Transcript.model_validate_json(Path(job.artifacts["transcript"]).read_text())
    assert transcript.segments == []
    assert transcript.headline.text == "GTA 6 IS COMING ON\nNOVEMBER 19 2026"
    assert transcript.headline.position == "bottom"

    req = translator.requests[0]
    assert req.headline == "GTA 6 IS COMING ON NOVEMBER 19 2026"
    assert "GTA6BR" not in req.onscreen_text and "2013" in req.onscreen_text

    translation = Translation.model_validate_json(Path(job.artifacts["translation"]).read_text())
    assert translation.headline == "GTA 6 CHEGA EM *19 DE NOVEMBRO DE 2026*"
    assert translation.headline_source == "GTA 6 IS COMING ON NOVEMBER 19 2026"


def test_single_image_and_duplicate_files(repo: PipelineRepository, tmp_path: Path):
    image = _image(tmp_path / "meme.jpg", "white")
    service = JobService(repo)
    runner = PipelineRunner(_ctx(repo, tmp_path), sleep=lambda _: None)

    job = runner.run_until_blocked(service.open_job_from_files([str(image)]).id)
    assert job.status == JobStatus.TRANSCRIBED
    assert repo.get_source(job.source_key).media_type == MediaType.IMAGE

    with pytest.raises(Exception, match="already used"):
        service.open_job_from_files([str(image)])

    with pytest.raises(ValueError, match="not found"):
        service.open_job_from_files([str(tmp_path / "missing.jpg")])


def test_local_translator_translates_headline(tmp_path: Path):
    engine_calls: List[List[str]] = []

    class Engine:
        def translate(self, texts):
            engine_calls.append(texts)
            return [f"PT:{t}" for t in texts]

    (tmp_path / "en_pt").mkdir()
    from underfind.backend.pipeline.local_translate import ModelStore
    store = ModelStore(root=tmp_path, engine_factory=lambda d: Engine(), auto_download=False)

    draft = LocalTranslator(store).translate(TranslationInput(
        target_language="pt", source_language="en", mode="subtitles",
        segments=[SegmentInput(index=0, start=0, end=1, text="hello", max_chars=20)],
        headline="WAIT FOR\\nTHE END",
    ))

    assert draft.headline == "PT:WAIT FOR\\nTHE END"
    assert engine_calls[0][-1] == "WAIT FOR\\nTHE END"


def test_from_files_api_and_headline_edit(repo: PipelineRepository, tmp_path: Path):
    image = _image(tmp_path / "post.jpg", "blue", headline=True)
    page = repo.save_page(PageProfile(display_name="P", handle="p"))
    runner = PipelineRunner(_ctx(repo, tmp_path), sleep=lambda _: None)
    app.dependency_overrides[get_pipeline_repo] = lambda: repo
    client = TestClient(app)

    try:
        res = client.post("/api/jobs/from-files", json={"files": [str(image)], "page_id": page.id, "local_only": True})
        assert res.status_code == 200
        job_id = res.json()["id"]
        assert res.json()["source"]["platform"] == "local"

        assert client.post("/api/jobs/from-files", json={"files": [str(tmp_path / "nope.jpg")]}).status_code == 400

        runner.run_until_blocked(job_id)
        edited = client.put(f"/api/jobs/{job_id}/translation", json={"headline": "GTA 6 EM *19/11*", "approve": True}).json()
        assert edited["headline"] == "GTA 6 EM *19/11*" and edited["approved"] is True
    finally:
        app.dependency_overrides.clear()
