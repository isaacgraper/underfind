from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from PIL import Image

from underfind.backend.core.constants import AI_MODES, DEFAULT_AI_MODE, BUDGET_TOLERANCE, JOBS_DIR, SOURCES_DIR, PHASH_FRAME_SECONDS
from underfind.backend.core.errors import DuplicateSourceError, PermanentStageError
from underfind.backend.core.logger import logger
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.pipeline.download import VIDEO_SUFFIXES, MediaDownloader, source_updates_from_info
from underfind.backend.pipeline.headline import auto_highlight, detect_headline
from underfind.backend.pipeline.dub import PiperTtsProvider, TtsProvider, build_tts, default_voice, mix_dub, synthesize_segments
from underfind.backend.core.niches import load_niche
from underfind.backend.pipeline.glossary import load_glossary
from underfind.backend.pipeline.media import extract_audio, extract_frame, has_audio_stream, probe_duration
from underfind.backend.pipeline.ocr import OnScreenTextDetector
from underfind.backend.pipeline.phash import dhash
from underfind.backend.pipeline.render import (
    band_crop,
    card_overlay,
    compose_still,
    concat_reels,
    place_media,
    render_card,
    resolve_layout,
    still_to_reel,
    video_to_reel,
)
from underfind.backend.pipeline.subtitles import build_cues, write_ass, write_srt
from underfind.backend.pipeline.transcribe import WhisperTranscriber
from underfind.backend.pipeline.translate import LLMTranslator, SegmentInput, TranslationDraft, TranslationInput, segment_budget
from underfind.backend.schemas.pipeline import (
    Headline,
    Job,
    Layout,
    MediaType,
    Platform,
    PageProfile,
    RenderTemplate,
    Transcript,
    TranslatedOnScreenText,
    TranslatedSegment,
    Translation,
)


def current_ai_mode() -> str:
    """AI_MODE env (set by --local / --online on the CLI). Anything unrecognized falls back to local."""
    mode = os.environ.get("AI_MODE", DEFAULT_AI_MODE).strip().lower()
    return mode if mode in AI_MODES else DEFAULT_AI_MODE


def build_translator(local: bool = True) -> Any:
    """Offline OPUS-MT on this machine, or the LLM gateway (config/llm.yaml) for jobs allowed to go online."""
    if not local:
        return LLMTranslator()

    from underfind.backend.pipeline.local_translate import LocalTranslator
    return LocalTranslator()


def resolve_local(job: Job, page: Optional[PageProfile], ai_mode: str) -> bool:
    """
    AI_MODE=local is a hard lock: always local. With AI_MODE=online, the job's override decides,
    otherwise the page's "local only" checkbox (checked by default).
    """
    if ai_mode != "online":
        return True

    if job.local_only is not None:
        return job.local_only

    return page.local_only if page is not None else True


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
    downloader: Any = field(default_factory=MediaDownloader)
    transcriber: WhisperTranscriber = field(default_factory=WhisperTranscriber)
    ocr: Optional[OnScreenTextDetector] = field(default_factory=OnScreenTextDetector)
    # Explicit backends (tests, custom setups) win; otherwise one is built per local/online choice and cached.
    translator: Any = None
    tts: Optional[TtsProvider] = None
    ai_mode: str = field(default_factory=current_ai_mode)
    _backends: dict = field(default_factory=dict, repr=False)

    def uses_local(self, job: Job, page: Optional[PageProfile]) -> bool:
        return resolve_local(job, page, self.ai_mode)

    def translator_for(self, local: bool) -> Any:
        if self.translator is not None:
            return self.translator

        key = ("translator", local)

        if key not in self._backends:
            self._backends[key] = build_translator(local)

        return self._backends[key]

    def tts_for(self, local: bool) -> TtsProvider:
        if self.tts is not None:
            return self.tts

        key = ("tts", local)

        if key not in self._backends:
            self._backends[key] = build_tts(local)

        return self._backends[key]


def _require_source(job: Job) -> None:
    if job.source is None:
        raise PermanentStageError(f"Job {job.id} has no source video record.")


def load_media(src_dir: Path) -> Optional[tuple[MediaType, List[Path]]]:
    """The downloaded media manifest (media.json), or None when the source hasn't been downloaded yet."""
    manifest = src_dir / "media.json"

    if not manifest.exists():
        # Sources downloaded before image support only have source.mp4.
        legacy = src_dir / "source.mp4"
        return (MediaType.VIDEO, [legacy]) if legacy.exists() else None

    data = json.loads(manifest.read_text(encoding="utf-8"))
    return MediaType(data["media_type"]), [src_dir / name for name in data["files"]]


def _save_media(src_dir: Path, files: List[Path]) -> tuple[MediaType, List[Path]]:
    """Normalizes downloaded files: a lone video becomes source.mp4; writes media.json."""
    files = [f for f in files if f.exists()]

    if not files:
        raise PermanentStageError(f"No media files in {src_dir}")

    if len(files) == 1 and files[0].suffix.lower() in VIDEO_SUFFIXES:
        target = src_dir / "source.mp4"

        if files[0] != target:
            files[0].replace(target)

        files = [target]
        media_type = MediaType.VIDEO
    elif len(files) == 1:
        media_type = MediaType.IMAGE
    else:
        media_type = MediaType.CAROUSEL

    (src_dir / "media.json").write_text(
        json.dumps({"media_type": media_type.value, "files": [f.name for f in files]}, indent=2),
        encoding="utf-8",
    )
    return media_type, files


def _copy_local_files(source_files: List[str], src_dir: Path) -> List[Path]:
    src_dir.mkdir(parents=True, exist_ok=True)
    copied: List[Path] = []

    for i, original in enumerate(source_files):
        path = Path(original).expanduser()

        if not path.exists():
            raise PermanentStageError(f"Local media file not found: {path}")

        target = src_dir / f"media_{i:02d}{path.suffix.lower()}"
        shutil.copyfile(path, target)
        copied.append(target)

    return copied


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_SUFFIXES


def download_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """
    found -> downloaded: fetch the post's media once per source (video, image or carousel; local files are copied),
    refresh metadata, hash the first frame/image, and stop if it's a reupload of a source another active job uses.
    """
    _require_source(job)
    src_dir = ctx.workspace.source_dir(job.source_key)
    media = load_media(src_dir)

    if media:
        logger.debug("Source %s already downloaded; reusing %s", job.source_key, src_dir)
        media_type, files = media
    else:
        if job.source.platform == Platform.LOCAL:
            files = _copy_local_files(job.source.media_files, src_dir)
            info = {}
        else:
            result = ctx.downloader.download(job.source.url, src_dir)
            files, info = result.media_files, result.info

        media_type, files = _save_media(src_dir, files)
        updates = source_updates_from_info(info)
        updates.update(media_type=media_type, media_files=[f.name for f in files])
        ctx.repo.upsert_source(job.source.model_copy(update=updates))

    first = files[0]

    if _is_video(first):
        duration = probe_duration(first)

        if not duration:
            raise PermanentStageError(f"Downloaded file for {job.source_key} has no readable duration (corrupt or not a video).")

        frame_path = extract_frame(first, min(PHASH_FRAME_SECONDS, duration / 2), src_dir / "frame.jpg")
    else:
        frame_path = src_dir / "frame.jpg"

        with Image.open(first) as image:
            image.convert("RGB").save(frame_path, quality=92)

    with Image.open(frame_path) as frame:
        phash = dhash(frame)

    ctx.repo.set_source_phash(job.source_key, phash)

    for similar, distance in ctx.repo.find_similar_sources(phash, exclude_key=job.source_key):
        other_job = ctx.repo.get_active_source_job_id(similar.key)

        if other_job and other_job != job.id:
            raise DuplicateSourceError(job.source_key, similar.key, other_job, distance)

    if media_type == MediaType.VIDEO:
        ctx.repo.set_artifact(job.id, "source_video", str(first))

    ctx.repo.set_artifact(job.id, "frame", str(frame_path))


def _brand_hints(job: Job) -> List[str]:
    source = job.source
    return [h for h in (source.author_handle, source.author_name) if h] if source else []


def transcribe_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """
    downloaded -> transcribed: speech to timestamped text + language (videos), OCR of on-screen text (every image,
    sampled video frames) and the headline band of the cover image or first frame.
    """
    _require_source(job)
    src_dir = ctx.workspace.source_dir(job.source_key)
    transcript_path = src_dir / "transcript.json"
    media = load_media(src_dir)

    if not media:
        raise PermanentStageError(f"Source media missing in {src_dir}; move the job back to 'found' to re-download.")

    media_type, files = media

    if transcript_path.exists():
        transcript = Transcript.model_validate_json(transcript_path.read_text(encoding="utf-8"))
        logger.debug("Source %s already transcribed; reusing %s", job.source_key, transcript_path)
    else:
        if media_type == MediaType.VIDEO:
            video_path = files[0]
            duration = probe_duration(video_path) or 0.0

            if has_audio_stream(video_path):
                audio_path = extract_audio(video_path, src_dir / "audio.wav")
                transcript = ctx.transcriber.transcribe(audio_path)
            else:
                logger.info("Source %s has no audio stream; storing an empty transcript", job.source_key)
                transcript = Transcript()

            transcript.duration_seconds = round(duration, 3)
            cover = src_dir / "frame.jpg"
        else:
            transcript = Transcript()
            video_path = None
            duration = 0.0
            cover = files[0]

        if ctx.ocr is not None:
            if media_type == MediaType.VIDEO:
                transcript.onscreen_text = ctx.ocr.detect(video_path, duration)
            else:
                transcript.onscreen_text = ctx.ocr.read_images([f for f in files if not _is_video(f)])

            transcript.headline = _detect_cover_headline(ctx, job, cover, transcript)

        transcript_path.write_text(json.dumps(transcript.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    updates = {"language": transcript.language}

    if transcript.onscreen_text is not None:
        updates["has_onscreen_text"] = bool(transcript.onscreen_text)

    ctx.repo.upsert_source(job.source.model_copy(update={k: v for k, v in updates.items() if v is not None}))
    ctx.repo.set_artifact(job.id, "transcript", str(transcript_path))


def _detect_cover_headline(ctx: StageContext, job: Job, cover: Path, transcript: Transcript) -> Optional[Headline]:
    """Headline band of the cover image (or first video frame), from OCR lines with boxes."""
    if not cover.exists() or not hasattr(ctx.ocr, "read_image") or not ctx.ocr.available():
        return None

    with Image.open(cover) as image:
        width, height = image.size

    cover_lines = [t for t in (transcript.onscreen_text or []) if t.box and t.media_file == cover.name]

    if not cover_lines:
        cover_lines = ctx.ocr.read_image(cover, media_file=cover.name)

    return detect_headline(cover_lines, width, height, brand_hints=_brand_hints(job), media_file=cover.name)


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


def _niche_hashtags(page: PageProfile) -> List[str]:
    preset = load_niche(page.niche)
    return preset.hashtags if preset else []


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
    glossary = load_glossary(page.niche, page.glossary)
    local = ctx.uses_local(job, page)
    translator = ctx.translator_for(local)

    inputs = [
        SegmentInput(index=i, start=s.start, end=s.end, text=s.text, max_chars=segment_budget(s.start, s.end, job.mode))
        for i, s in enumerate(transcript.segments)
        if s.text.strip()
    ]
    headline_source = " ".join(transcript.headline.text.split()) if transcript.headline else ""
    headline_lines = set(transcript.headline.text.splitlines()) if transcript.headline else set()
    brand_line = transcript.headline.brand_text if transcript.headline else None
    # The headline travels on its own; its OCR lines and the brand tag are not translated twice.
    onscreen = [
        t.text for t in (transcript.onscreen_text or [])
        if t.text not in headline_lines and t.text != brand_line
    ]
    source_caption = job.source.caption or job.source.title or ""

    if not inputs and not onscreen and not source_caption.strip() and not headline_source:
        draft = TranslationDraft(caption="", hashtags=[])
    else:
        draft = translator.translate(TranslationInput(
            target_language=page.language,
            source_language=transcript.language,
            mode=job.mode,
            segments=inputs,
            source_caption=source_caption,
            headline=headline_source or None,
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

        for fixed in translator.shorten(page.language, over, glossary):
            if fixed.index in by_index and fixed.text.strip():
                by_index[fixed.index] = fixed.text.strip()

    translation = Translation(
        local=local,
        source_language=transcript.language,
        target_language=page.language,
        page_id=page.id,
        mode=job.mode,
        model=getattr(translator, "model", None),
        segments=[
            TranslatedSegment(index=s.index, start=s.start, end=s.end, source_text=s.text, text=by_index[s.index], max_chars=s.max_chars)
            for s in inputs
        ],
        headline=auto_highlight(draft.headline.strip()) if headline_source else "",
        headline_source=headline_source,
        caption=draft.caption.strip(),
        hashtags=_merge_hashtags(draft.hashtags, [*page.default_hashtags, *_niche_hashtags(page)]),
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

    tts = ctx.tts_for(ctx.uses_local(job, page))
    voice = page.tts_voice or default_voice(page.language, getattr(tts, "voices", None))
    clips = synthesize_segments(translation.segments, voice, tts, job_dir / "dub_clips", video_duration)
    audio_path = mix_dub(video_path, clips, video_duration, job_dir / "dub_audio.wav")

    report = {
        "local": isinstance(tts, PiperTtsProvider),
        "voice": voice,
        "clips": [
            {"index": c.index, "start": c.start, "duration": round(c.duration, 3), "speedup": c.speedup}
            for c in clips
        ],
    }
    (job_dir / "dub.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    ctx.repo.set_artifact(job.id, "dub_audio", str(audio_path))


def _outputs_dir(ctx: StageContext, job: Job) -> Path:
    out = ctx.workspace.job_dir(job.id) / "output"

    if out.exists():
        shutil.rmtree(out)

    out.mkdir(parents=True)
    return out


def render_stage(
    job: Job,
    ctx: StageContext,
) -> None:
    """
    voiced -> rendered: the page's outputs in its template.
      reel      9:16 mp4; videos keep motion (+ burned subtitles, dub audio), images get a slow zoom and the page's
                audio bed (or silence); carousels play each image in turn
      post      4:5 jpg of the cover
      carousel  4:5 jpg per image, the headline card on the cover
    The headline_card layout crops the source's own headline band and re-types the translated headline under the
    page's brand tag; letterbox and full_bleed keep the media as is.
    """
    _require_source(job)
    page = _require_page(ctx, job)
    template = _template_for(ctx, page)
    translation = load_translation(ctx, job.id)
    transcript = _load_transcript(ctx, job)
    src_dir = ctx.workspace.source_dir(job.source_key)
    media = load_media(src_dir)

    if not media:
        raise PermanentStageError(f"Source media missing in {src_dir}; move the job back to 'found' to re-download.")

    media_type, files = media
    cover_path = src_dir / "frame.jpg" if media_type == MediaType.VIDEO else files[0]
    headline = transcript.headline

    with Image.open(cover_path) as cover_image:
        cover = cover_image.convert("RGB")

    layout = resolve_layout(template, media_type, headline, translation.headline, cover.size)
    brand_tag = page.brand_tag or page.handle.upper()
    out_dir = _outputs_dir(ctx, job)
    artifacts: dict = {}

    def slide(image: Image.Image, is_cover: bool, canvas: tuple) -> tuple[Image.Image, Optional[Image.Image], Layout]:
        """Composed still, card overlay (reel use) and layout for one image."""
        slide_layout = layout if is_cover else (Layout.LETTERBOX if layout == Layout.HEADLINE_CARD else layout)

        if slide_layout == Layout.HEADLINE_CARD:
            crop = band_crop(image.size, headline)
            image = image.crop(crop) if crop else image
            card_h = int(canvas[1] * template.card_ratio)
            card = render_card(canvas[0], card_h, brand_tag, translation.headline, template)
            placed_h = place_media(image, slide_layout, canvas, template)[0].size[1]
            overlay = card_overlay(card, placed_h, canvas, template)
            return compose_still(image, slide_layout, canvas, template, card), overlay, slide_layout

        return compose_still(image, slide_layout, canvas, template), None, slide_layout

    stills = [cover] if media_type == MediaType.VIDEO else []

    for f in ([] if media_type == MediaType.VIDEO else files):
        if f.suffix.lower() in VIDEO_SUFFIXES:
            frame = extract_frame(f, 0.5, out_dir / f"{f.stem}_frame.jpg")
            with Image.open(frame) as img:
                stills.append(img.convert("RGB"))
            frame.unlink(missing_ok=True)
        else:
            with Image.open(f) as img:
                stills.append(img.convert("RGB"))

    post_canvas = (template.width, template.post_height)

    if "post" in page.outputs:
        composed, _, _ = slide(stills[0], True, post_canvas)
        path = out_dir / "post.jpg"
        composed.save(path, quality=95)
        artifacts["post"] = path

    if "carousel" in page.outputs:
        for i, image in enumerate(stills, start=1):
            composed, _, _ = slide(image, i == 1, post_canvas)
            path = out_dir / f"carousel_{i:02d}.jpg"
            composed.save(path, quality=95)
            artifacts[f"carousel_{i:02d}"] = path

    if "reel" in page.outputs:
        reel_canvas = (template.width, template.height)
        reel_path = out_dir / "reel.mp4"
        audio_bed = Path(page.audio_bed_path).expanduser() if page.audio_bed_path else None

        if media_type == MediaType.VIDEO:
            _, overlay, reel_layout = slide(cover, True, reel_canvas)
            crop = band_crop(cover.size, headline) if reel_layout == Layout.HEADLINE_CARD else None
            dub = Path(job.artifacts["dub_audio"]) if job.artifacts.get("dub_audio") else None
            video_to_reel(files[0], reel_layout, template, reel_path, crop=crop, overlay=overlay,
                          segments=translation.segments, audio_path=dub)
        else:
            parts: List[Path] = []

            for i, image in enumerate(stills):
                composed, overlay, slide_layout = slide(image, i == 0, reel_canvas)
                layer = composed if overlay is None else compose_still(
                    image.crop(band_crop(image.size, headline)) if i == 0 and band_crop(image.size, headline) else image,
                    slide_layout, reel_canvas, template,
                )
                part = out_dir / f"reel_part_{i:02d}.mp4"
                still_to_reel(layer, overlay, template, part, template.still_seconds, audio_bed)
                parts.append(part)

            concat_reels(parts, reel_path)

            for part in parts:
                part.unlink(missing_ok=True)

        artifacts["reel"] = reel_path

    if not artifacts:
        raise PermanentStageError(f"Page {page.handle} has no outputs configured.")

    for name, path in artifacts.items():
        ctx.repo.set_artifact(job.id, name, str(path))

    logger.info("Job %s rendered %s (%s layout)", job.id, ", ".join(artifacts), layout.value)
