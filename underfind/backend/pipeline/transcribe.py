from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Optional

from underfind.backend.core.constants import (
    DEFAULT_WHISPER_MODEL,
    DEFAULT_WHISPER_DEVICE,
    DEFAULT_WHISPER_COMPUTE_TYPE,
)
from underfind.backend.core.logger import logger
from underfind.backend.schemas.pipeline import Transcript, TranscriptSegment, TranscriptWord


class WhisperTranscriber:
    """
    Speech-to-text with faster-whisper: language auto-detection, VAD (skips music-only parts) and word timestamps.
    Configure via env: WHISPER_MODEL (tiny/base/small/medium/large-v3), WHISPER_DEVICE (auto/cpu/cuda),
    WHISPER_COMPUTE_TYPE (int8 for CPU, float16 for GPU).
    The model downloads on first use and stays loaded for the process lifetime.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ):
        self.model_name = model_name or os.environ.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL)
        self.device = device or os.environ.get("WHISPER_DEVICE", DEFAULT_WHISPER_DEVICE)
        self.compute_type = compute_type or os.environ.get("WHISPER_COMPUTE_TYPE", DEFAULT_WHISPER_COMPUTE_TYPE)
        self._model: Any = None
        self._lock = threading.Lock()

    def _get_model(self) -> Any:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                logger.info("Loading Whisper model '%s' (%s, %s)", self.model_name, self.device, self.compute_type)
                self._model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)

            return self._model

    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> Transcript:
        model = self._get_model()
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
        )

        segments = [
            TranscriptSegment(
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                text=seg.text.strip(),
                words=[
                    TranscriptWord(start=round(w.start, 3), end=round(w.end, 3), word=w.word, probability=w.probability)
                    for w in (seg.words or [])
                ],
            )
            for seg in segments_iter
        ]

        logger.debug("Transcribed %s: %d segments, language=%s (p=%.2f)", audio_path.name, len(segments), info.language, info.language_probability)
        return Transcript(
            language=info.language,
            language_probability=round(info.language_probability, 3),
            duration_seconds=round(info.duration, 3),
            model=self.model_name,
            segments=segments,
        )
