from __future__ import annotations

from typing import Optional, List
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

from underfind.backend.core.constants import (
    SUPPORTED_TRANSCRIPT_LANGUAGES,
    DEFAULT_HOOK_MAX_SECONDS,
    DEFAULT_HOOK_MIN_SECONDS,
)
from underfind.backend.schemas.video import VideoItem
from underfind.backend.schemas.blueprint import VideoBlueprint, TranscriptLine, ModelingPromptRequest
from underfind.backend.core.logger import logger


class TranscriptService:
    """Service for extracting transcripts, isolating opening hooks, and building modeling blueprints."""

    SUPPORTED_LANGUAGES = SUPPORTED_TRANSCRIPT_LANGUAGES

    @classmethod
    def get_transcript(
        cls,
        video_id: str,
    ) -> Optional[List[TranscriptLine]]:
        """
        Retrieves official or auto-generated transcript for a given video ID.
        Returns a list of TranscriptLine objects with timestamps.
        """
        logger.debug(
            "Requesting transcript for video ID: %s with languages: %s",
            video_id,
            cls.SUPPORTED_LANGUAGES,
        )

        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=cls.SUPPORTED_LANGUAGES,
            )
            segments = [
                TranscriptLine(
                    text=entry.get("text", "").replace("\n", " ").strip(),
                    start=round(float(entry.get("start", 0)), 2),
                    duration=round(float(entry.get("duration", 0)), 2),
                )
                for entry in transcript_list
                if entry.get("text")
            ]

            logger.trace("Retrieved %d transcript segments for video ID: %s", len(segments), video_id)
            return segments

        except (TranscriptsDisabled, NoTranscriptFound) as e:
            logger.info("Transcript not available for video %s: %s", video_id, e)
            return None

        except Exception as e:
            logger.warning("Failed to retrieve transcript for %s: %s", video_id, e)
            return None

    @classmethod
    def extract_hook(
        cls,
        segments: List[TranscriptLine],
        max_seconds: float = DEFAULT_HOOK_MAX_SECONDS,
    ) -> tuple[str, float]:
        """
        Extracts speech spoken within the initial 'max_seconds' window,
        which represents the critical opening hook in vertical short-form video.
        """
        if not segments:
            return "", 0.0

        hook_parts = []
        total_time = 0.0

        for seg in segments:
            if seg.start <= max_seconds or total_time < DEFAULT_HOOK_MIN_SECONDS:
                hook_parts.append(seg.text)
                total_time = seg.start + seg.duration
            else:
                break

        hook_text = " ".join(hook_parts).strip()
        final_duration = round(min(total_time, max_seconds + 2.0), 2)

        logger.trace("Extracted opening hook (%.1fs): '%s'", final_duration, hook_text[:80])
        return hook_text, final_duration

    @classmethod
    def create_blueprint(
        cls,
        video: VideoItem,
        custom_niche: Optional[str] = None,
    ) -> VideoBlueprint:
        """
        Constructs a complete VideoBlueprint containing transcript, hook, and a prompt ready for LLM script modeling.
        """
        logger.debug("Creating creative blueprint for video ID: %s (niche: %s)", video.video_id, custom_niche)

        segments = cls.get_transcript(video.video_id) or []
        full_text = " ".join(s.text for s in segments) if segments else (video.description or "Transcript not available.")
        hook_text, hook_dur = cls.extract_hook(segments, max_seconds=DEFAULT_HOOK_MAX_SECONDS)

        if not hook_text and segments:
            hook_text = segments[0].text
            hook_dur = segments[0].duration

        prompt = cls.generate_modeling_prompt(
            ModelingPromptRequest(
                video_id=video.video_id,
                target_niche=custom_niche or "my target niche",
            ),
            video=video,
            hook=hook_text,
            transcript=full_text,
        )

        blueprint = VideoBlueprint(
            video_id=video.video_id,
            title=video.title,
            channel_title=video.channel_title or "Channel",
            views=video.views or 0,
            subscribers=video.subscribers or 0,
            viral_ratio=video.viral_ratio,
            video_url=video.video_url or f"https://www.youtube.com/watch?v={video.video_id}",
            duration_seconds=video.duration_seconds or 0,
            is_short=video.is_short,
            hook_text=hook_text or "Visual hook or uncaptioned opening detected",
            hook_duration=hook_dur,
            full_transcript=full_text,
            transcript_segments=segments,
            suggested_prompt=prompt,
        )

        logger.trace("Blueprint constructed for video ID: %s (hook length: %.1fs)", video.video_id, hook_dur)
        return blueprint

    @classmethod
    def generate_modeling_prompt(
        cls,
        req: ModelingPromptRequest,
        video: VideoItem,
        hook: str,
        transcript: str,
    ) -> str:
        """
        Generates a calibrated script engineering prompt for LLMs (Gemini / Claude / ChatGPT).
        """
        niche = req.target_niche or "my target niche"
        tone = req.tone or "fast-paced, high-retention"

        prompt = f"""You are an elite short-form video retention engineer and creative scriptwriter specializing in YouTube Shorts, Instagram Reels, and TikTok.

Analyze this viral outlier creative which generated a Viral Ratio of {video.viral_ratio}x (Views: {video.views:,} | Subscribers: {video.subscribers:,}):

=== ORIGINAL OUTLIER SOURCE ===
- Title: {video.title}
- Channel: {video.channel_title}
- Duration: {video.duration_seconds}s
- Opening Hook (0-5s):
  "{hook}"
- Full Transcript:
  \"\"\"{transcript[:3000]}\"\"\"

=== MODELING OBJECTIVE ===
Reverse-engineer the underlying psychological architecture and draft an original, un-copied script adapted specifically for:
- Target Niche: {niche}
- Tone of Voice: {tone}

=== OUTPUT SPECIFICATION ===
1. **Hook Deconstruction:** What cognitive trigger does this opening hook activate? (Curiosity gap, counter-intuitive premise, pattern interrupt, loss aversion?)
2. **Retention Pacing:** Map out the pacing milestones (0-3s Hook, 3-15s Tension escalation, 15-45s Core value delivery, 45-60s Seamless loop re-hook).
3. **Adapted 60-Second Script:**
   - **[00:00 - 00:03] The Hook:** 1 punchy, arresting sentence.
   - **[00:03 - 00:15] The Curiosity Gap:** Why the viewer must stay until the end.
   - **[00:15 - 00:45] The Core Insight:** 3 fast-paced, high-density value points.
   - **[00:45 - 00:55] The Climax:** The unexpected takeaway.
   - **[00:55 - 00:60] The Seamless Loop:** The closing sentence that flows directly back into the opening hook.
4. **Visual Direction & B-Roll Cues (for MedPy clipping):**
   - Timestamp cut points and visual prompt tags for raw footage compilation.
"""
        return prompt.strip()
