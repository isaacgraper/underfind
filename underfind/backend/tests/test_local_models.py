from __future__ import annotations

import io
import json
import wave
import zipfile
from pathlib import Path
from typing import Dict, List

import pytest

from underfind.backend.core.errors import PermanentStageError
from underfind.backend.pipeline.dub import EdgeTtsProvider, PiperTtsProvider, build_tts
from underfind.backend.pipeline.local_translate import LocalTranslator, ModelStore, base_language
from underfind.backend.pipeline.media import probe_duration
from underfind.backend.pipeline.stages import StageContext, build_translator, current_ai_mode, resolve_local
from underfind.backend.schemas.pipeline import Job, PageProfile
from underfind.backend.pipeline.translate import LLMTranslator, SegmentInput, TranslationInput

EN_PT = {
    "Rockstar just dropped the ZQ0X trailer.": "A Rockstar acabou de lançar o trailer ZQ0X.",
    "ZQ1X is back in ZQ0X.": "ZQ1X está de volta em ZQ0X.",
    "Trailer 3 is here": "O trailer 3 chegou",
    "Look at this": "Olha isso",
}
ES_EN = {"ZQ0X se ve increíble": "ZQ0X looks incredible"}
EN_PT_PIVOT = {"ZQ0X looks incredible": "ZQ0X parece incrível"}


class DictEngine:
    def __init__(self, table: Dict[str, str], calls: List[List[str]]):
        self.table = table
        self.calls = calls

    def translate(self, texts: List[str]) -> List[str]:
        self.calls.append(texts)
        return [self.table.get(t, f"<{t}>") for t in texts]


def _store(tmp_path: Path, pairs: Dict[str, Dict[str, str]], calls: List[List[str]]) -> ModelStore:
    for pair in pairs:
        (tmp_path / pair).mkdir(parents=True)

    return ModelStore(
        root=tmp_path,
        engine_factory=lambda directory: DictEngine(pairs[directory.name], calls),
        auto_download=False,
    )


def test_base_language():
    assert base_language("pt-BR") == "pt"
    assert base_language("es_MX") == "es"
    assert base_language(None) is None


def test_local_translator_masks_glossary_and_splits_caption(tmp_path: Path):
    calls: List[List[str]] = []
    translator = LocalTranslator(_store(tmp_path, {"en_pt": EN_PT}, calls))

    draft = translator.translate(TranslationInput(
        target_language="pt-BR",
        source_language="en",
        mode="subtitles",
        segments=[
            SegmentInput(index=0, start=0, end=2, text="Rockstar just dropped the GTA VI trailer.", max_chars=34),
            SegmentInput(index=1, start=2, end=4, text="Lucia is back in GTA VI.", max_chars=34),
        ],
        source_caption="Trailer 3 is here #gta6 #rockstar\nLook at this @gta6news",
        glossary=["Lucia", "GTA VI", "GTA 6"],
    ))

    assert [s.text for s in draft.segments] == [
        "A Rockstar acabou de lançar o trailer GTA VI.",
        "Lucia está de volta em GTA VI.",
    ]
    assert draft.caption == "O trailer 3 chegou\nOlha isso"
    assert draft.hashtags == ["#gta6", "#rockstar"]
    assert len(calls) == 1
    assert translator.model == "local/opus-mt:en-pt"


def test_local_translator_pivots_through_english(tmp_path: Path):
    calls: List[List[str]] = []
    translator = LocalTranslator(_store(tmp_path, {"es_en": ES_EN, "en_pt": EN_PT_PIVOT}, calls))

    draft = translator.translate(TranslationInput(
        target_language="pt-BR", source_language="es", mode="subtitles",
        segments=[SegmentInput(index=0, start=0, end=2, text="Vice City se ve increíble", max_chars=34)],
        glossary=["Vice City"],
    ))

    assert draft.segments[0].text == "Vice City parece incrível"
    assert translator.model == "local/opus-mt:es-en+en-pt"


def test_local_translator_retries_unmasked_when_placeholder_is_lost(tmp_path: Path):
    calls: List[List[str]] = []
    table = {"Welcome to ZQ0X": "Bem-vindo à cidade", "Welcome to Vice City": "Bem-vindo a Vice City"}
    translator = LocalTranslator(_store(tmp_path, {"en_pt": table}, calls))

    draft = translator.translate(TranslationInput(
        target_language="pt", source_language="en", mode="subtitles",
        segments=[SegmentInput(index=0, start=0, end=2, text="Welcome to Vice City", max_chars=34)],
        glossary=["Vice City"],
    ))

    assert draft.segments[0].text == "Bem-vindo a Vice City"
    assert calls == [["Welcome to ZQ0X"], ["Welcome to Vice City"]]


def test_same_language_passes_through(tmp_path: Path):
    translator = LocalTranslator(_store(tmp_path, {}, []))
    draft = translator.translate(TranslationInput(
        target_language="pt-BR", source_language="pt", mode="subtitles",
        segments=[SegmentInput(index=0, start=0, end=2, text="Já saiu o trailer", max_chars=34)],
    ))

    assert draft.segments[0].text == "Já saiu o trailer"


def test_missing_model_is_permanent(tmp_path: Path):
    translator = LocalTranslator(_store(tmp_path, {}, []))

    with pytest.raises(PermanentStageError, match="en->pt"):
        translator.translate(TranslationInput(
            target_language="pt", source_language="en", mode="subtitles",
            segments=[SegmentInput(index=0, start=0, end=2, text="hi", max_chars=20)],
        ))


def test_model_store_downloads_argos_package_once(tmp_path: Path):
    archive = io.BytesIO()

    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("translate-en_pt-1_9/metadata.json", "{}")
        z.writestr("translate-en_pt-1_9/sentencepiece.model", "spm")
        z.writestr("translate-en_pt-1_9/model/model.bin", "weights")
        z.writestr("translate-en_pt-1_9/stanza/en/tokenize.pt", "skip")

    index = [{"from_code": "en", "to_code": "pt", "package_version": "1.9", "links": ["https://models.test/en_pt.argosmodel"]}]
    fetched: List[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return json.dumps(index).encode() if url.endswith(".json") else archive.getvalue()

    built: List[Path] = []
    store = ModelStore(root=tmp_path, engine_factory=lambda d: built.append(d) or "engine", fetch=fetch, auto_download=True)

    assert store.engine("en", "pt") == "engine"
    assert store.engine("en", "pt") == "engine"
    assert (tmp_path / "en_pt" / "model" / "model.bin").read_text() == "weights"
    assert (tmp_path / "en_pt" / "sentencepiece.model").exists()
    assert not (tmp_path / "en_pt" / "stanza").exists()
    assert fetched == [fetched[0], "https://models.test/en_pt.argosmodel"] and len(built) == 1


def test_piper_voice_url_and_download(tmp_path: Path):
    assert PiperTtsProvider.voice_url("pt_BR-faber-medium").endswith("/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx")

    fetched: List[str] = []
    provider = PiperTtsProvider(voices_dir=tmp_path, fetch=lambda url: fetched.append(url) or b"x", auto_download=True)
    provider.ensure_voice("pt_BR-faber-medium")
    provider.ensure_voice("pt_BR-faber-medium")

    assert len(fetched) == 2
    assert fetched[1].endswith(".onnx.json")

    offline = PiperTtsProvider(voices_dir=tmp_path / "empty", auto_download=False)
    with pytest.raises(PermanentStageError):
        offline.ensure_voice("es_MX-ald-medium")


class _FakePiperVoice:
    def synthesize_wav(self, text: str, wav_file: wave.Wave_write) -> None:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x10" * 22050)


def test_piper_synthesize_writes_wav(tmp_path: Path):
    (tmp_path / "v.onnx").write_bytes(b"m")
    (tmp_path / "v.onnx.json").write_bytes(b"{}")
    provider = PiperTtsProvider(voices_dir=tmp_path, loader=lambda path: _FakePiperVoice(), auto_download=False)

    out = provider.synthesize("Olá", "v", tmp_path / "out.wav")

    assert probe_duration(out) == pytest.approx(1.0, abs=0.05)


def test_backend_builders():
    assert isinstance(build_translator(), LocalTranslator)
    assert isinstance(build_translator(local=False), LLMTranslator)
    assert isinstance(build_tts(), PiperTtsProvider)
    assert isinstance(build_tts(local=False), EdgeTtsProvider)


@pytest.mark.parametrize("ai_mode, job_override, page_local, expected", [
    ("local", False, False, True),    # global local is a hard lock
    ("local", None, False, True),
    ("online", None, True, True),     # page checkbox checked (default)
    ("online", None, False, False),   # page unchecked
    ("online", True, False, True),    # job forces local
    ("online", False, True, False),   # job allows online
    ("bogus", False, False, True),
])
def test_resolve_local(ai_mode, job_override, page_local, expected):
    job = Job(id="j", source_key="youtube:x", local_only=job_override)
    page = PageProfile(display_name="p", handle="p", local_only=page_local)

    assert resolve_local(job, page, ai_mode if ai_mode in ("local", "online") else "local") is expected


def test_current_ai_mode(monkeypatch):
    monkeypatch.delenv("AI_MODE", raising=False)
    assert current_ai_mode() == "local"

    monkeypatch.setenv("AI_MODE", "ONLINE")
    assert current_ai_mode() == "online"

    monkeypatch.setenv("AI_MODE", "cloud")
    assert current_ai_mode() == "local"


def test_context_builds_one_backend_per_choice(tmp_path):
    ctx = StageContext(repo=None, ai_mode="online")

    assert isinstance(ctx.translator_for(True), LocalTranslator)
    assert isinstance(ctx.translator_for(False), LLMTranslator)
    assert ctx.translator_for(True) is ctx.translator_for(True)
    assert isinstance(ctx.tts_for(True), PiperTtsProvider)


def test_brazilian_model_preferred_then_base(tmp_path: Path):
    calls: List[List[str]] = []
    both = LocalTranslator(_store(tmp_path / "a", {"en_pb": {"Look at this": "Olha só"}, "en_pt": {"Look at this": "Veja isto"}}, calls))
    only_pt = LocalTranslator(_store(tmp_path / "b", {"en_pt": {"Look at this": "Veja isto"}}, calls))
    req = TranslationInput(target_language="pt-BR", source_language="en", mode="subtitles",
                           segments=[SegmentInput(index=0, start=0, end=2, text="Look at this", max_chars=30)])

    assert both.translate(req).segments[0].text == "Olha só"
    assert both.model == "local/opus-mt:en-pb"
    assert only_pt.translate(req).segments[0].text == "Veja isto"
