from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol

from underfind.backend.core.constants import (
    DEFAULT_TTS_VOICES,
    DUB_MAX_SPEEDUP,
    DUB_BACKGROUND_VOLUME,
    DUB_SAMPLE_RATE,
)
from underfind.backend.core.errors import PermanentStageError
from underfind.backend.core.logger import logger
from underfind.backend.pipeline.media import has_audio_stream, probe_duration, run_ffmpeg
from underfind.backend.schemas.pipeline import TranslatedSegment


class TtsProvider(Protocol):
    def synthesize(self, text: str, voice: str, out_path: Path) -> Path:
        ...


class EdgeTtsProvider:
    """Free neural voices via Microsoft Edge's online TTS (edge-tts package). Needs network access to speech.platform.bing.com."""

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy or os.environ.get("TTS_PROXY") or None

    def synthesize(self, text: str, voice: str, out_path: Path) -> Path:
        import edge_tts

        async def _run() -> None:
            await edge_tts.Communicate(text, voice, proxy=self.proxy).save(str(out_path))

        asyncio.run(_run())

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(f"TTS produced no audio for voice {voice}")

        return out_path


def default_voice(language: str) -> str:
    """Voice for a page language: exact tag first (pt-BR), then base language (pt)."""
    if language in DEFAULT_TTS_VOICES:
        return DEFAULT_TTS_VOICES[language]

    base = language.split("-")[0]

    if base in DEFAULT_TTS_VOICES:
        return DEFAULT_TTS_VOICES[base]

    raise PermanentStageError(f"No default TTS voice for language '{language}'; set tts_voice on the page profile.")


@dataclass
class PlacedClip:
    index: int
    path: Path
    start: float
    duration: float
    speedup: float


def fit_clip(
    raw_path: Path,
    slot_seconds: float,
    out_path: Path,
) -> tuple[Path, float, float]:
    """
    Converts a TTS clip to WAV and speeds it up (pitch-preserving atempo) when it overruns its slot,
    capped at DUB_MAX_SPEEDUP so speech stays natural. Returns (path, duration, speedup).
    """
    duration = probe_duration(raw_path) or 0.0
    speedup = 1.0

    if slot_seconds > 0 and duration > slot_seconds:
        speedup = min(duration / slot_seconds, DUB_MAX_SPEEDUP)

    filters = [f"atempo={speedup:.4f}"] if speedup > 1.0 else []
    args = ["-i", str(raw_path), "-ac", "1", "-ar", str(DUB_SAMPLE_RATE)]

    if filters:
        args += ["-filter:a", ",".join(filters)]

    run_ffmpeg([*args, str(out_path)])
    return out_path, duration / speedup, speedup


def synthesize_segments(
    segments: List[TranslatedSegment],
    voice: str,
    tts: TtsProvider,
    work_dir: Path,
    video_duration: float,
) -> List[PlacedClip]:
    """TTS per segment, each fitted to the time until the next segment starts (or the video ends)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    spoken = [s for s in segments if s.text.strip()]
    clips: List[PlacedClip] = []

    for i, seg in enumerate(spoken):
        next_start = spoken[i + 1].start if i + 1 < len(spoken) else video_duration
        slot = max(0.1, next_start - seg.start)
        raw = tts.synthesize(seg.text, voice, work_dir / f"seg_{seg.index:03d}.mp3")
        fitted, duration, speedup = fit_clip(raw, slot, work_dir / f"seg_{seg.index:03d}.wav")

        if duration > slot + 0.05:
            logger.warning("Dub segment %d still overruns its slot by %.2fs after %.2fx speedup", seg.index, duration - slot, speedup)

        clips.append(PlacedClip(index=seg.index, path=fitted, start=seg.start, duration=duration, speedup=round(speedup, 3)))

    return clips


def mix_dub(
    video_path: Path,
    clips: List[PlacedClip],
    video_duration: float,
    out_path: Path,
    background_volume: Optional[float] = None,
) -> Path:
    """
    Final audio track: original audio ducked to background level (keeps game sound/music) with the
    dubbed clips placed at their segment start times, trimmed to the video's length.
    """
    bg_volume = background_volume if background_volume is not None else float(os.environ.get("DUB_BACKGROUND_VOLUME", DUB_BACKGROUND_VOLUME))
    inputs: List[str] = []
    filters: List[str] = []
    labels: List[str] = []
    offset = 0

    if has_audio_stream(video_path):
        inputs += ["-i", str(video_path)]
        filters.append(f"[0:a]aresample={DUB_SAMPLE_RATE},aformat=channel_layouts=mono,volume={bg_volume}[bg]")
        labels.append("[bg]")
        offset = 1

    for i, clip in enumerate(clips):
        inputs += ["-i", str(clip.path)]
        delay_ms = int(round(clip.start * 1000))
        filters.append(f"[{i + offset}:a]adelay={delay_ms}:all=1[c{i}]")
        labels.append(f"[c{i}]")

    if not labels:
        # Nothing to mix: a silent track keeps the render step uniform.
        run_ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r={DUB_SAMPLE_RATE}:cl=mono", "-t", f"{video_duration:.3f}", str(out_path)])
        return out_path

    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,"
        f"apad,atrim=0:{video_duration:.3f}[out]"
    )
    run_ffmpeg([*inputs, "-filter_complex", ";".join(filters), "-map", "[out]", "-ac", "1", "-ar", str(DUB_SAMPLE_RATE), str(out_path)])
    return out_path
