from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from PIL import Image

from underfind.backend.core.constants import DEFAULT_TRANSLATION_BACKEND, BUDGET_TOLERANCE, JOBS_DIR, SOURCES_DIR, PHASH_FRAME_SECONDS
from underfind.backend.core.errors import DuplicateSourceError, PermanentStageError
from underfind.backend.core.logger import logger
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.pipeline.download import YtDlpDownloader, source_updates_from_info
from underfind.backend.pipeline.dub import TtsProvider, build_tts, default_voice, mix_dub, synthesize_segments
from underfind.backend.pipeline.glossary import load_glossary
from underfind.backend.pipeline.media import extract_audio, extract_frame, has_audio_stream, probe_duration
from underfind.backend.pipeline.ocr import OnScreenTextDetector
from underfind.backend.pipeline.phash import dhash
from underfind.backend.pipeline.subtitles import build_cues, write_ass, write_srt
from underfind.backend.pipeline.transcribe import WhisperTranscriber
from underfind.backend.pipeline.translate import LLMTranslator, SegmentInput, TranslationDraft, TranslationInput, segment_budget
from underfind.backend.schemas.pipeline import (
    Job,
    PageProfile,
    RenderTemplate,
    Transcript,
    TranslatedOnScreenText,
    TranslatedSegment,
    Translation,
)


def build_translator() -> Any:
    """TRANSLATION_BACKEND=local (offline OPUS-MT, default) or llm (LLM gateway, opt-in)."""
    backend = os.environ.get("TRANSLATION_BACKEND", DEFAULT_TRANSLATION_BACKEND).lower()

    if backend == "llm":
        return LLMTranslator()

    from underfind.backend.pipeline.local_translate import LocalTranslator
    return LocalTranslator()


@dataclass
class Workspace:
    """Artifact locations. Source files are shared by every job (page) localizing the same video."""

    sources_dir: Path = SOURCES_DIR
    jobs_dir: Path = JOBS_DIR

    def source_dir(self, source_key: str) -> Path:
        return self.sources_dir / source_key.replace(":", "_")

    def job_dir(self, job_id: str) -> Path:
        return self.jobs_dir / job_id


@dataclass
class StageContext:
    repo: PipelineRepository
    workspace: Workspace = field(default_factory=Workspace)
    downloader: YtDlpDownloader = field(default_factory=YtDlpDownloader)
    transcriber: WhisperTranscriber = field(default_factory=WhisperTranscriber)
    ocr: Optional[OnScreenTextDetector] = field(default_factory=OnScreenTextDetector)
    translator: Any = field(default_factory=lambda: build_translator())
    tts: TtsProvider = field(default_factory=build_tts)


def _require_source(job: Job) -> None:
    if job.source is None:
        raise PermanentStageError(f"Job {job.id} has no source video record.")


def download_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """
    found -> downloaded: fetch the video once per source, refresh metadata, hash a reference frame,
    and stop if it's a reupload of a source another active job already uses.
    """
    _require_source(job)
    src_dir = ctx.workspace.source_dir(job.source_key)
    video_path = src_dir / "source.mp4"

    if video_path.exists():
        logger.debug("Source %s already downloaded; reusing %s", job.source_key, video_path)
    else:
        result = ctx.downloader.download(job.source.url, src_dir)
        updates = source_updates_from_info(result.info)
        ctx.repo.upsert_source(job.source.model_copy(update=updates))

    duration = probe_duration(video_path)

    if not duration:
        raise PermanentStageError(f"Downloaded file for {job.source_key} has no readable duration (corrupt or not a video).")

    frame_path = extract_frame(video_path, min(PHASH_FRAME_SECONDS, duration / 2), src_dir / "frame.jpg")

    with Image.open(frame_path) as frame:
        phash = dhash(frame)

    ctx.repo.set_source_phash(job.source_key, phash)

    for similar, distance in ctx.repo.find_similar_sources(phash, exclude_key=job.source_key):
        other_job = ctx.repo.get_active_source_job_id(similar.key)

        if other_job and other_job != job.id:
            raise DuplicateSourceError(job.source_key, similar.key, other_job, distance)

    ctx.repo.set_artifact(job.id, "source_video", str(video_path))
    ctx.repo.set_artifact(job.id, "frame", str(frame_path))


def transcribe_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """downloaded -> transcribed: speech to timestamped text + language, and flag burned-in on-screen text."""
    _require_source(job)
    src_dir = ctx.workspace.source_dir(job.source_key)
    video_path = src_dir / "source.mp4"
    transcript_path = src_dir / "transcript.json"

    if not video_path.exists():
        raise PermanentStageError(f"Source video missing at {video_path}; move the job back to 'found' to re-download.")

    if transcript_path.exists():
        transcript = Transcript.model_validate_json(transcript_path.read_text(encoding="utf-8"))
        logger.debug("Source %s already transcribed; reusing %s", job.source_key, transcript_path)
    else:
        duration = probe_duration(video_path) or 0.0

        if has_audio_stream(video_path):
            audio_path = extract_audio(video_path, src_dir / "audio.wav")
            transcript = ctx.transcriber.transcribe(audio_path)
        else:
            logger.info("Source %s has no audio stream; storing an empty transcript", job.source_key)
            transcript = Transcript()

        transcript.duration_seconds = round(duration, 3)

        if ctx.ocr is not None:
            transcript.onscreen_text = ctx.ocr.detect(video_path, duration)

        transcript_path.write_text(json.dumps(transcript.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    updates = {"language": transcript.language}

    if transcript.onscreen_text is not None:
        updates["has_onscreen_text"] = bool(transcript.onscreen_text)

    ctx.repo.upsert_source(job.source.model_copy(update={k: v for k, v in updates.items() if v is not None}))
    ctx.repo.set_artifact(job.id, "transcript", str(transcript_path))


def _load_transcript(ctx: StageContext, job: Job) -> Transcript:
    path = ctx.workspace.source_dir(job.source_key) / "transcript.json"

    if not path.exists():
        raise PermanentStageError(f"Transcript missing at {path}; move the job back to 'downloaded' to re-transcribe.")

    return Transcript.model_validate_json(path.read_text(encoding="utf-8"))


def _require_page(ctx: StageContext, job: Job) -> PageProfile:
    page = ctx.repo.get_page(job.page_id) if job.page_id is not None else None

    if page is None:
        raise PermanentStageError(f"Job {job.id} has no target page; assign one before translating.")

    return page


def translation_path(ctx: StageContext, job_id: str) -> Path:
    return ctx.workspace.job_dir(job_id) / "translation.json"


def load_translation(ctx: StageContext, job_id: str) -> Translation:
    path = translation_path(ctx, job_id)

    if not path.exists():
        raise PermanentStageError(f"Translation missing at {path}; move the job back to 'transcribed' to re-translate.")

    return Translation.model_validate_json(path.read_text(encoding="utf-8"))


def save_translation(ctx: StageContext, job_id: str, translation: Translation) -> Path:
    path = translation_path(ctx, job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(translation.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _merge_hashtags(generated: List[str], defaults: List[str]) -> List[str]:
    merged: List[str] = []
    seen: set[str] = set()

    for tag in [*defaults, *generated]:
        clean = "#" + tag.strip().lstrip("#").replace(" ", "")

        if len(clean) > 1 and clean.lower() not in seen:
            seen.add(clean.lower())
            merged.append(clean)

    return merged


def translate_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """
    transcribed -> translated: timing-budgeted translation of every segment, localized caption, hashtags
    and on-screen text for the target page. Lines over budget get one condensing pass.
    The result waits at the review gate unless the page auto-approves.
    """
    _require_source(job)
    page = _require_page(ctx, job)
    transcript = _load_transcript(ctx, job)
    glossary = load_glossary()

    inputs = [
        SegmentInput(index=i, start=s.start, end=s.end, text=s.text, max_chars=segment_budget(s.start, s.end, job.mode))
        for i, s in enumerate(transcript.segments)
        if s.text.strip()
    ]
    onscreen = [t.text for t in (transcript.onscreen_text or [])]
    source_caption = job.source.caption or job.source.title or ""

    if not inputs and not onscreen and not source_caption.strip():
        draft = TranslationDraft(caption="", hashtags=[])
    else:
        draft = ctx.translator.translate(TranslationInput(
            target_language=page.language,
            source_language=transcript.language,
            mode=job.mode,
            segments=inputs,
            source_caption=source_caption,
            onscreen_text=onscreen,
            glossary=glossary,
        ))

    by_index = {s.index: s.text.strip() for s in draft.segments}
    missing = [s.index for s in inputs if not by_index.get(s.index)]

    if missing:
        raise RuntimeError(f"Translation skipped segments {missing}")

    over = [
        SegmentInput(index=s.index, start=s.start, end=s.end, text=by_index[s.index], max_chars=s.max_chars)
        for s in inputs
        if len(by_index[s.index]) > s.max_chars * BUDGET_TOLERANCE
    ]

    if over:
        logger.debug("Job %s: %d translated lines over budget; condensing", job.id, len(over))

        for fixed in ctx.translator.shorten(page.language, over, glossary):
            if fixed.index in by_index and fixed.text.strip():
                by_index[fixed.index] = fixed.text.strip()

    translation = Translation(
        source_language=transcript.language,
        target_language=page.language,
        page_id=page.id,
        mode=job.mode,
        model=getattr(ctx.translator, "model", None),
        segments=[
            TranslatedSegment(index=s.index, start=s.start, end=s.end, source_text=s.text, text=by_index[s.index], max_chars=s.max_chars)
            for s in inputs
        ],
        caption=draft.caption.strip(),
        hashtags=_merge_hashtags(draft.hashtags, page.default_hashtags),
        onscreen_text=[TranslatedOnScreenText(source=o.source, text=o.text) for o in draft.onscreen_text],
        approved=page.auto_approve_translation,
        approved_at=datetime.now(timezone.utc).isoformat() if page.auto_approve_translation else None,
    )

    path = save_translation(ctx, job.id, translation)
    ctx.repo.set_artifact(job.id, "translation", str(path))
    ctx.repo.set_translation_approved(job.id, translation.approved)


def _template_for(ctx: StageContext, page: PageProfile) -> RenderTemplate:
    template = ctx.repo.get_template(page.template_id) if page.template_id is not None else None
    return template or RenderTemplate(name="default")


def voice_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """
    translated -> voiced (after approval): styled subtitles (ASS for burning, SRT for platforms) in every mode;
    in dub mode also TTS per segment, fitted to its slot and mixed over the ducked original audio.
    """
    _require_source(job)
    page = _require_page(ctx, job)
    translation = load_translation(ctx, job.id)

    if not translation.approved:
        raise PermanentStageError("Translation is not approved yet.")

    template = _template_for(ctx, page)
    job_dir = ctx.workspace.job_dir(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)

    cues = build_cues(translation.segments, template)
    ass_path = write_ass(cues, template, job_dir / "subs.ass")
    srt_path = write_srt(cues, job_dir / "subs.srt")
    ctx.repo.set_artifact(job.id, "subtitles_ass", str(ass_path))
    ctx.repo.set_artifact(job.id, "subtitles_srt", str(srt_path))

    if job.mode != "dub":
        return

    video_path = ctx.workspace.source_dir(job.source_key) / "source.mp4"
    video_duration = probe_duration(video_path)

    if not video_duration:
        raise PermanentStageError(f"Source video missing or unreadable at {video_path}.")

    voice = page.tts_voice or default_voice(page.language, getattr(ctx.tts, "voices", None))
    clips = synthesize_segments(translation.segments, voice, ctx.tts, job_dir / "dub_clips", video_duration)
    audio_path = mix_dub(video_path, clips, video_duration, job_dir / "dub_audio.wav")

    report = {
        "voice": voice,
        "clips": [
            {"index": c.index, "start": c.start, "duration": round(c.duration, 3), "speedup": c.speedup}
            for c in clips
        ],
    }
    (job_dir / "dub.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    ctx.repo.set_artifact(job.id, "dub_audio", str(audio_path))
