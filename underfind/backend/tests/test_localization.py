from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from underfind.backend.core.errors import PermanentStageError
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo, get_pipeline_runner
from underfind.backend.main import app
from underfind.backend.pipeline.dub import default_voice, fit_clip, mix_dub, PlacedClip
from underfind.backend.pipeline.media import probe_duration, run_ffmpeg
from underfind.backend.pipeline.runner import PipelineRunner
from underfind.backend.pipeline.stages import StageContext, Workspace
from underfind.backend.pipeline.subtitles import build_cues, max_line_chars, wrap_words, write_ass, write_srt
from underfind.backend.pipeline.translate import (
    ClaudeTranslator,
    SegmentInput,
    TranslationDraft,
    TranslationInput,
    segment_budget,
)
from underfind.backend.pipeline.download import DownloadResult
from underfind.backend.schemas.pipeline import (
    JobStatus,
    PageProfile,
    RenderTemplate,
    Transcript,
    TranslatedSegment,
    TranscriptSegment,
    Translation,
)
from underfind.backend.services.job_service import JobService

YT_URL = "https://www.youtube.com/shorts/BBBBBBBBBBB"

SOURCE_LINES = [
    (0.0, 2.0, "Rockstar just dropped the third GTA VI trailer."),
    (2.0, 4.0, "Lucia is back and Vice City looks insane."),
    (4.0, 5.5, "Comment your favorite detail."),
]
PT_LINES = {
    0: "A Rockstar soltou o terceiro trailer de GTA VI.",
    1: "A Lucia voltou e Vice City tá absurda.",
    2: "Comenta teu detalhe favorito.",
}


def _video(path: Path, seconds: float = 6) -> Path:
    run_ffmpeg([
        "-f", "lavfi", "-i", f"testsrc=size=320x568:rate=10:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
        "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(path),
    ])
    return path


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> Path:
    return _video(tmp_path_factory.mktemp("loc") / "gameplay.mp4")


class FakeDownloader:
    def __init__(self, video: Path):
        self.video = video

    def download(self, url: str, dest_dir: Path) -> DownloadResult:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.video, dest_dir / "source.mp4")
        return DownloadResult(dest_dir / "source.mp4", {"title": "GTA VI trailer 3", "description": "Trailer 3 is here #gta6"})


class FakeTranscriber:
    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> Transcript:
        return Transcript(language="en", segments=[TranscriptSegment(start=a, end=b, text=t) for a, b, t in SOURCE_LINES])


class FakeTranslator:
    model = "fake-translator"

    def __init__(self, overrides: Optional[Dict[int, str]] = None, shortened: Optional[Dict[int, str]] = None):
        self.overrides = overrides or {}
        self.shortened = shortened or {}
        self.requests: List[TranslationInput] = []
        self.shorten_calls: List[List[SegmentInput]] = []

    def translate(self, req: TranslationInput) -> TranslationDraft:
        self.requests.append(req)
        return TranslationDraft.model_validate({
            "segments": [{"index": s.index, "text": self.overrides.get(s.index, PT_LINES[s.index])} for s in req.segments],
            "caption": "O trailer 3 de GTA VI chegou 🔥 Qual detalhe você viu?",
            "hashtags": ["gta6", "#trailer3", "#gamesbr"],
            "onscreen_text": [],
        })

    def shorten(self, target_language: str, segments: List[SegmentInput], glossary: List[str]):
        self.shorten_calls.append(segments)
        return [SimpleNamespace(index=s.index, text=self.shortened[s.index]) for s in segments if s.index in self.shortened]


class FakeTts:
    def __init__(self):
        self.calls: List[tuple[str, str]] = []

    def synthesize(self, text: str, voice: str, out_path: Path) -> Path:
        self.calls.append((text, voice))
        seconds = max(0.5, len(text) / 14)
        run_ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds:.2f}", "-c:a", "libmp3lame", str(out_path)])
        return out_path


@pytest.fixture
def repo(tmp_path: Path) -> PipelineRepository:
    return PipelineRepository(db_path=tmp_path / "pipeline.sqlite3")


def _runner(repo: PipelineRepository, tmp_path: Path, clip: Path, translator=None, tts=None) -> PipelineRunner:
    ctx = StageContext(
        repo=repo,
        workspace=Workspace(sources_dir=tmp_path / "sources", jobs_dir=tmp_path / "jobs"),
        downloader=FakeDownloader(clip),
        transcriber=FakeTranscriber(),
        ocr=None,
        translator=translator or FakeTranslator(),
        tts=tts or FakeTts(),
    )
    return PipelineRunner(ctx, sleep=lambda _: None)


def _page(repo: PipelineRepository, **kwargs) -> PageProfile:
    return repo.save_page(PageProfile(display_name="GTA VI Brasil", handle="gta6br", language="pt-BR", default_hashtags=["#gta6", "#gtavi"], **kwargs))


# ------------------------------------------------------------ budgets & subtitles


def test_segment_budget_by_mode():
    assert segment_budget(0.0, 2.0, "subtitles") == 34
    assert segment_budget(0.0, 2.0, "dub") == 28
    assert segment_budget(0.0, 0.3, "subtitles") == 12


def test_wrap_and_cues_split_long_lines():
    template = RenderTemplate(name="t")
    width = max_line_chars(template)
    assert width == 26

    assert wrap_words("uma frase curta", 27) == ["uma frase curta"]
    assert all(len(line) <= 27 for line in wrap_words("palavras " * 20, 27))

    long_text = "A Rockstar confirmou que o mapa de Leonida é duas vezes maior que Los Santos e cheio de segredos"
    cues = build_cues([TranslatedSegment(index=0, start=1.0, end=7.0, source_text="x", text=long_text, max_chars=100)], template)

    assert len(cues) == 2
    assert all(len(c.lines) <= 2 for c in cues)
    assert cues[0].start == 1.0 and cues[-1].end == 7.0
    assert cues[0].end == cues[1].start


def test_ass_and_srt_output(tmp_path: Path):
    template = RenderTemplate(name="t", subtitle_color="#FFD400", subtitle_outline_color="#000000", subtitle_position_y=0.75)
    segments = [TranslatedSegment(index=0, start=0.0, end=2.5, source_text="x", text="Vice City {tá} absurda demais mesmo, olha isso", max_chars=40)]
    cues = build_cues(segments, template)

    ass = write_ass(cues, template, tmp_path / "s.ass").read_text()
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "&H0000D4FF" in ass
    assert ",480,1" in ass  # MarginV = 1920 * (1 - 0.75)
    assert "Dialogue: 0,0:00:00.00,0:00:02.50,Default,,0,0,0,,Vice City (tá) absurda\\Ndemais mesmo, olha isso" in ass

    srt = write_srt(cues, tmp_path / "s.srt").read_text()
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,500\nVice City {tá} absurda\ndemais mesmo, olha isso")


def test_ass_renders_with_ffmpeg(tmp_path: Path, clip: Path):
    template = RenderTemplate(name="t", width=320, height=568, subtitle_font_size=24)
    cues = build_cues([TranslatedSegment(index=0, start=0.0, end=2.0, source_text="x", text="Teste de legenda", max_chars=30)], template)
    ass = write_ass(cues, template, tmp_path / "s.ass")

    run_ffmpeg(["-i", str(clip), "-t", "1", "-vf", f"subtitles={ass}", "-an", str(tmp_path / "out.mp4")])
    assert (tmp_path / "out.mp4").stat().st_size > 0


# -------------------------------------------------------------------- dub


def test_default_voice():
    assert default_voice("pt-BR") == "pt-BR-AntonioNeural"
    assert default_voice("es-AR") == "es-MX-JorgeNeural"

    with pytest.raises(PermanentStageError):
        default_voice("ja")


def test_fit_clip_speeds_up_overruns_with_cap(tmp_path: Path):
    raw = tmp_path / "raw.mp3"
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:a", "libmp3lame", str(raw)])

    _, duration, speedup = fit_clip(raw, 2.5, tmp_path / "a.wav")
    assert speedup == pytest.approx(1.2, abs=0.03)
    assert duration == pytest.approx(2.5, abs=0.1)
    assert probe_duration(tmp_path / "a.wav") == pytest.approx(2.5, abs=0.15)

    _, _, capped = fit_clip(raw, 1.0, tmp_path / "b.wav")
    assert capped == 1.35

    _, _, untouched = fit_clip(raw, 5.0, tmp_path / "c.wav")
    assert untouched == 1.0


def test_mix_dub_matches_video_length(tmp_path: Path, clip: Path):
    voice = tmp_path / "v.wav"
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=600:duration=1", str(voice)])
    clips = [PlacedClip(0, voice, 0.5, 1.0, 1.0), PlacedClip(1, voice, 3.0, 1.0, 1.0)]

    out = mix_dub(clip, clips, 6.0, tmp_path / "dub.wav", background_volume=0.1)
    assert probe_duration(out) == pytest.approx(6.0, abs=0.1)


# ------------------------------------------------------------- translator


class _FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _claude(response) -> tuple[ClaudeTranslator, _FakeMessages]:
    messages = _FakeMessages(response)
    return ClaudeTranslator(client=SimpleNamespace(messages=messages), model="claude-opus-5-5", effort="medium"), messages


def _req() -> TranslationInput:
    return TranslationInput(
        target_language="pt-BR",
        source_language="en",
        mode="subtitles",
        segments=[SegmentInput(index=0, start=0, end=2, text="Hello Vice City", max_chars=34)],
        glossary=["Vice City"],
    )


def test_claude_translator_request_shape():
    draft = TranslationDraft(segments=[{"index": 0, "text": "Fala, Vice City"}], caption="c", hashtags=["#gta6"])
    translator, messages = _claude(SimpleNamespace(stop_reason="end_turn", parsed_output=draft))

    assert translator.translate(_req()) is draft
    assert messages.kwargs["model"] == "claude-opus-5-5"
    assert messages.kwargs["output_format"] is TranslationDraft
    assert messages.kwargs["output_config"] == {"effort": "medium"}
    assert '"max_chars": 34' in messages.kwargs["messages"][0]["content"]
    assert "Vice City" in messages.kwargs["messages"][0]["content"]


def test_claude_translator_refusal_is_permanent_and_truncation_retryable():
    refused, _ = _claude(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(PermanentStageError):
        refused.translate(_req())

    truncated, _ = _claude(SimpleNamespace(stop_reason="max_tokens", parsed_output=None))
    with pytest.raises(RuntimeError):
        truncated.translate(_req())


# --------------------------------------------------------- pipeline stages


def test_pipeline_waits_for_page_then_review(repo: PipelineRepository, tmp_path: Path, clip: Path):
    translator = FakeTranslator()
    runner = _runner(repo, tmp_path, clip, translator=translator)
    job_id = JobService(repo).open_job_from_url(YT_URL).id

    assert runner.run_until_blocked(job_id).status == JobStatus.TRANSCRIBED
    assert repo.list_runnable_job_ids([JobStatus.TRANSCRIBED]) == []

    page = _page(repo)
    repo.assign_page(job_id, page.id)
    assert repo.list_runnable_job_ids([JobStatus.TRANSCRIBED]) == [job_id]

    job = runner.run_until_blocked(job_id)
    assert job.status == JobStatus.TRANSLATED
    assert job.translation_approved is False
    assert repo.list_runnable_job_ids([JobStatus.TRANSLATED]) == []

    req = translator.requests[0]
    assert req.target_language == "pt-BR"
    assert req.source_caption == "Trailer 3 is here #gta6"
    assert [s.max_chars for s in req.segments] == [34, 34, 25]
    assert "Vice City" in req.glossary

    translation = runner.ctx.repo.get_job(job_id)
    assert Path(translation.artifacts["translation"]).exists()


def test_review_edit_approve_and_voice_subtitles(repo: PipelineRepository, tmp_path: Path, clip: Path):
    runner = _runner(repo, tmp_path, clip)
    page = _page(repo)
    job_id = JobService(repo).open_job_from_url(YT_URL, page_id=page.id).id
    runner.run_until_blocked(job_id)

    app.dependency_overrides[get_pipeline_repo] = lambda: repo
    app.dependency_overrides[get_pipeline_runner] = lambda: runner
    client = TestClient(app)

    try:
        translation = client.get(f"/api/jobs/{job_id}/translation").json()
        assert translation["segments"][1]["source_text"] == SOURCE_LINES[1][2]
        assert translation["segments"][1]["text"] == PT_LINES[1]
        assert translation["hashtags"] == ["#gta6", "#gtavi", "#trailer3", "#gamesbr"]
        assert translation["approved"] is False

        edited = client.put(f"/api/jobs/{job_id}/translation", json={
            "segments": [{"index": 1, "text": "A Lucia voltou e Vice City tá insana."}],
            "caption": "Trailer 3 de GTA VI! Qual detalhe você pegou?",
        }).json()
        assert edited["edited"] is True and edited["approved"] is False
        assert client.put(f"/api/jobs/{job_id}/translation", json={"segments": [{"index": 9, "text": "x"}]}).status_code == 400

        approved = client.post(f"/api/jobs/{job_id}/translation/approve").json()
        assert approved["approved"] is True and approved["approved_at"]

        client.post(f"/api/jobs/{job_id}/run")
        job = client.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "voiced"
        assert "dub_audio" not in job["artifacts"]

        srt = Path(job["artifacts"]["subtitles_srt"]).read_text()
        assert "A Lucia voltou e Vice City tá insana." in srt.replace("\n", " ")
        assert Path(job["artifacts"]["subtitles_ass"]).exists()

        assert client.put(f"/api/jobs/{job_id}/translation", json={"caption": "late edit"}).status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_auto_approved_dub_page_runs_to_voiced(repo: PipelineRepository, tmp_path: Path, clip: Path):
    tts = FakeTts()
    runner = _runner(repo, tmp_path, clip, tts=tts)
    page = _page(repo, auto_approve_translation=True)
    job_id = JobService(repo).open_job_from_url(YT_URL, page_id=page.id, mode="dub").id

    job = runner.run_until_blocked(job_id)

    assert job.status == JobStatus.VOICED
    assert [voice for _, voice in tts.calls] == ["pt-BR-AntonioNeural"] * 3
    assert probe_duration(Path(job.artifacts["dub_audio"])) == pytest.approx(6.0, abs=0.15)
    assert Path(job.artifacts["subtitles_ass"]).exists()


def test_over_budget_lines_get_condensed(repo: PipelineRepository, tmp_path: Path, clip: Path):
    long_line = "A Rockstar finalmente soltou o terceiro trailer oficial de GTA VI hoje de manhã"
    translator = FakeTranslator(overrides={0: long_line}, shortened={0: "Saiu o trailer 3 de GTA VI!"})
    runner = _runner(repo, tmp_path, clip, translator=translator)
    page = _page(repo)
    job_id = JobService(repo).open_job_from_url(YT_URL, page_id=page.id).id
    runner.run_until_blocked(job_id)

    # Segment 2 (29 chars in a 1.5s / 25-char slot) is over budget too; only lines past the tolerance are sent.
    assert [s.index for s in translator.shorten_calls[0]] == [0, 2]
    job = repo.get_job(job_id)
    translation = Translation.model_validate_json(Path(job.artifacts["translation"]).read_text())
    assert translation.segments[0].text == "Saiu o trailer 3 de GTA VI!"


def test_moving_back_resets_approval(repo: PipelineRepository, tmp_path: Path, clip: Path):
    runner = _runner(repo, tmp_path, clip)
    page = _page(repo, auto_approve_translation=True)
    job_id = JobService(repo).open_job_from_url(YT_URL, page_id=page.id).id
    runner.run_next(job_id)
    runner.run_next(job_id)
    job = runner.run_next(job_id)
    assert job.status == JobStatus.TRANSLATED and job.translation_approved is True

    back = repo.transition(job_id, JobStatus.TRANSCRIBED, note="re-translate")
    assert back.translation_approved is False
