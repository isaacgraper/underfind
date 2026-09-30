from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from underfind.backend.core.constants import (
    DEFAULT_TRANSLATION_MODEL,
    DEFAULT_TRANSLATION_EFFORT,
    TRANSLATION_MAX_TOKENS,
    SUBTITLE_CHARS_PER_SECOND,
    DUB_CHARS_PER_SECOND,
    MIN_SEGMENT_CHARS,
)
from underfind.backend.core.errors import PermanentStageError
from underfind.backend.core.logger import logger

SYSTEM_PROMPT = """You localize short-form gaming videos (Reels, Shorts, TikToks) about GTA VI for social media pages in other languages.

You receive the timestamped transcript of one video, split into numbered segments, plus its original caption and any text burned into the video. Produce the version a native creator in the target language would post.

Segments:
- Return exactly one translation per input segment, with the same index.
- Each segment has a max_chars budget: the line must be read (subtitles) or spoken (dub) within that segment's time. Stay within it; condense wording rather than dropping meaning.
- Write how gamers in the target language actually talk: natural phrasing and gaming slang, not a literal translation. Keep the tone and energy of the original.
- Keep numbers, dates, prices and platform names accurate.
- Glossary terms (game titles, place and character names) stay exactly as written.

Caption and hashtags:
- The caption is the post text for the target page: a short hook line, one or two lines of context from the video, then a question or call to comment. Do not mention the source creator or that it is a translation.
- 5 to 10 hashtags mixing target-language tags with global ones; always include #gta6.

On-screen text: translate each item so it can be overlaid on the video; keep it as short as the original."""


class _DraftSegment(BaseModel):
    index: int
    text: str


class _DraftOnScreen(BaseModel):
    source: str
    text: str


class TranslationDraft(BaseModel):
    segments: List[_DraftSegment] = Field(default_factory=list)
    caption: str
    hashtags: List[str] = Field(default_factory=list)
    onscreen_text: List[_DraftOnScreen] = Field(default_factory=list)


class _ShortenedSegments(BaseModel):
    segments: List[_DraftSegment]


@dataclass
class SegmentInput:
    index: int
    start: float
    end: float
    text: str
    max_chars: int


@dataclass
class TranslationInput:
    target_language: str
    source_language: Optional[str]
    mode: str
    segments: List[SegmentInput]
    source_caption: Optional[str] = None
    onscreen_text: List[str] = field(default_factory=list)
    glossary: List[str] = field(default_factory=list)


def segment_budget(
    start: float,
    end: float,
    mode: str,
) -> int:
    """Max characters that fit a segment's duration at a comfortable reading (subtitles) or speaking (dub) rate."""
    rate = DUB_CHARS_PER_SECOND if mode == "dub" else SUBTITLE_CHARS_PER_SECOND
    return max(MIN_SEGMENT_CHARS, int((end - start) * rate))


class ClaudeTranslator:
    """
    Translates a transcript with the Claude API into validated structured output.
    Env: ANTHROPIC_API_KEY (or another SDK credential source), TRANSLATION_MODEL, TRANSLATION_EFFORT.
    """

    def __init__(
        self,
        client: Any = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
    ):
        self._client = client
        self._lock = threading.Lock()
        self.model = model or os.environ.get("TRANSLATION_MODEL", DEFAULT_TRANSLATION_MODEL)
        self.effort = effort or os.environ.get("TRANSLATION_EFFORT", DEFAULT_TRANSLATION_EFFORT)

    def _get_client(self) -> Any:
        with self._lock:
            if self._client is None:
                import anthropic
                self._client = anthropic.Anthropic()

            return self._client

    def _parse(self, user_content: str, output_format: type[BaseModel]) -> BaseModel:
        import anthropic

        try:
            response = self._get_client().messages.parse(
                model=self.model,
                max_tokens=TRANSLATION_MAX_TOKENS,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_content}],
                output_config={"effort": self.effort},
                output_format=output_format,
            )
        except (anthropic.BadRequestError, anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError) as err:
            raise PermanentStageError(f"Translation request rejected: {err}") from err

        if response.stop_reason == "refusal":
            raise PermanentStageError("Translation refused by the model's safety classifiers.")

        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise RuntimeError(f"Translation output incomplete (stop_reason={response.stop_reason}).")

        return response.parsed_output

    def translate(self, req: TranslationInput) -> TranslationDraft:
        payload = {
            "target_language": req.target_language,
            "source_language": req.source_language or "auto-detect",
            "mode": req.mode,
            "glossary": req.glossary,
            "segments": [
                {"index": s.index, "start": s.start, "end": s.end, "max_chars": s.max_chars, "text": s.text}
                for s in req.segments
            ],
            "original_caption": req.source_caption or "",
            "onscreen_text": req.onscreen_text,
        }
        logger.debug("Translating %d segments to %s with %s", len(req.segments), req.target_language, self.model)
        return self._parse(json.dumps(payload, ensure_ascii=False, indent=1), TranslationDraft)

    def shorten(
        self,
        target_language: str,
        segments: List[SegmentInput],
        glossary: List[str],
    ) -> List[_DraftSegment]:
        """Second pass for lines over budget: condense each to its max_chars in the same language."""
        payload = {
            "task": f"These {target_language} lines are too long for their time slot. Rewrite each one to fit max_chars, keeping meaning and tone. Return the same indexes.",
            "glossary": glossary,
            "segments": [{"index": s.index, "max_chars": s.max_chars, "text": s.text} for s in segments],
        }
        return self._parse(json.dumps(payload, ensure_ascii=False, indent=1), _ShortenedSegments).segments
