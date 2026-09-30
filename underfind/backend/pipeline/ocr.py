from __future__ import annotations

import importlib.util
import tempfile
import threading
from pathlib import Path
from typing import Any, List, Optional

from underfind.backend.core.constants import (
    OCR_SAMPLE_FRAMES,
    OCR_MIN_CONFIDENCE,
    OCR_MIN_TEXT_LENGTH,
)
from underfind.backend.core.logger import logger
from underfind.backend.pipeline.media import extract_frame
from underfind.backend.schemas.pipeline import OnScreenText

# Platform watermarks and handles are not content that needs translating.
_IGNORED_TEXT = {"tiktok", "instagram", "reels", "youtube", "shorts"}


class OnScreenTextDetector:
    """
    Samples frames and runs OCR to find burned-in text (captions, titles) that a translated version must cover.
    Optional: needs the `rapidocr-onnxruntime` package (poetry install -E ocr). Without it, detection is skipped.
    """

    def __init__(
        self,
        sample_frames: int = OCR_SAMPLE_FRAMES,
        min_confidence: float = OCR_MIN_CONFIDENCE,
    ):
        self.sample_frames = sample_frames
        self.min_confidence = min_confidence
        self._engine: Any = None
        self._lock = threading.Lock()

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("rapidocr_onnxruntime") is not None

    def _get_engine(self) -> Any:
        with self._lock:
            if self._engine is None:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR()

            return self._engine

    def _read_text(self, image_path: Path) -> List[tuple[str, float]]:
        result, _elapsed = self._get_engine()(str(image_path))
        return [(item[1], float(item[2])) for item in (result or [])]

    @staticmethod
    def _keep(text: str) -> bool:
        clean = text.strip()
        return (
            len(clean) >= OCR_MIN_TEXT_LENGTH
            and not clean.startswith("@")
            and clean.lower() not in _IGNORED_TEXT
        )

    def detect(
        self,
        video_path: Path,
        duration_seconds: float,
    ) -> Optional[List[OnScreenText]]:
        if not self.available():
            logger.debug("rapidocr-onnxruntime not installed; skipping on-screen text detection")
            return None

        if not duration_seconds or duration_seconds <= 0:
            return []

        step = duration_seconds / (self.sample_frames + 1)
        found: List[OnScreenText] = []
        seen: set[str] = set()

        with tempfile.TemporaryDirectory() as tmp:
            for i in range(1, self.sample_frames + 1):
                at = round(step * i, 2)
                frame = extract_frame(video_path, at, Path(tmp) / f"ocr_{i}.jpg")

                for text, confidence in self._read_text(frame):
                    key = text.strip().lower()

                    if confidence < self.min_confidence or not self._keep(text) or key in seen:
                        continue

                    seen.add(key)
                    found.append(OnScreenText(at_seconds=at, text=text.strip(), confidence=round(confidence, 3)))

        return found
