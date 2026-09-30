from __future__ import annotations

from pathlib import Path
from typing import List, Dict

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DATABASE_PATH = DATA_DIR / "cache.sqlite3"
FRONTEND_DIST_DIR = ROOT_DIR / "underfind" / "frontend" / "dist"

# Network & Host
DEFAULT_HOST: str = "0.0.0.0"
DEFAULT_PORT: int = 8000

# Cache Configuration
DEFAULT_TTL_HOURS: int = 720  # 30 days persistent local cache

# YouTube Query & Filtering Defaults
DEFAULT_REGION: str = "BR"
DEFAULT_MAX_RESULTS: int = 25
MAX_ALLOWED_RESULTS: int = 50
DEFAULT_ORDER: str = "relevance"
DEFAULT_ORDER_OUTLIERS: str = "viewCount"

# Outlier Thresholds
DEFAULT_MIN_VIEWS: int = 10000
DEFAULT_MAX_SUBSCRIBERS: int = 50000
DEFAULT_MIN_VIRAL_RATIO: float = 3.0
MIN_SUBSCRIBER_BASE: int = 100
VIRAL_THRESHOLD_EXTREME: float = 10.0
VIRAL_THRESHOLD_OUTLIER: float = 3.0
VIRAL_THRESHOLD_NEUTRAL: float = 1.0

# Video Duration Boundaries (seconds)
MAX_STANDARD_SHORT_DURATION: int = 60
MAX_EXTENDED_SHORT_DURATION: int = 180

# Transcript & Hook Extraction
DEFAULT_HOOK_MAX_SECONDS: float = 5.0
DEFAULT_HOOK_MIN_SECONDS: float = 3.0
SUPPORTED_TRANSCRIPT_LANGUAGES: List[str] = ["en", "en-US", "pt", "pt-BR", "es"]

# AI Modeling Prompt Defaults
DEFAULT_MODELING_TONE: str = "fast-paced, high-retention"
DEFAULT_BENCHMARK_HOOK_SCORE: float = 88.5

# Kanban Pipeline Defaults
DEFAULT_IDEA_STATUS: str = "backlog"
IDEA_STATUSES: List[str] = ["backlog", "in_progress", "done"]

# Showcase & MCP Limits
DEFAULT_SHOWCASE_LIMIT: int = 12
DEFAULT_MCP_MAX_RESULTS: int = 10

# MedPy Raw Footage Cut Markers
DEFAULT_MEDPY_CUT_MARKERS: List[Dict[str, str]] = [
    {"segment": "hook", "start": "00:00", "end": "00:03", "pacing": "fast"},
    {"segment": "curiosity_gap", "start": "00:03", "end": "00:15", "pacing": "medium"},
    {"segment": "core_delivery", "start": "00:15", "end": "00:45", "pacing": "rapid_cuts_2.5s"},
    {"segment": "climax", "start": "00:45", "end": "00:55", "pacing": "intense"},
    {"segment": "loop", "start": "00:55", "end": "00:60", "pacing": "seamless_rehook"},
]

# Service Metadata
SERVICE_NAME: str = "underfind-api"
SERVICE_VERSION: str = "2.1.0"

# Pipeline Storage
SOURCES_DIR = DATA_DIR / "sources"
JOBS_DIR = DATA_DIR / "jobs"
PAGE_ASSETS_DIR = DATA_DIR / "pages"

# Pipeline Defaults
DEFAULT_TARGET_LANGUAGE: str = "pt-BR"
DEFAULT_LOCALIZATION_MODE: str = "subtitles"
LOCALIZATION_MODES: List[str] = ["subtitles", "dub"]
PHASH_MAX_DISTANCE: int = 6

# YouTube Data API Quota (units reset daily at midnight Pacific Time)
YOUTUBE_DAILY_QUOTA: int = 10000
YOUTUBE_QUOTA_TIMEZONE: str = "America/Los_Angeles"
YOUTUBE_QUOTA_COSTS: Dict[str, int] = {
    "search.list": 100,
    "videos.list": 1,
    "channels.list": 1,
}
API_MAX_RETRIES: int = 3
API_BACKOFF_BASE_SECONDS: float = 1.0

# Pipeline Worker
STAGE_MAX_ATTEMPTS: int = 3
STAGE_BACKOFF_BASE_SECONDS: float = 5.0
JOB_LOCK_STALE_MINUTES: int = 60
WORKER_POLL_INTERVAL_SECONDS: float = 30.0
WORKER_MAX_PARALLEL_JOBS: int = 2

# Download (yt-dlp)
YTDLP_FORMAT: str = "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"
PHASH_FRAME_SECONDS: float = 1.0

# Transcription (faster-whisper)
DEFAULT_WHISPER_MODEL: str = "small"
DEFAULT_WHISPER_DEVICE: str = "auto"
DEFAULT_WHISPER_COMPUTE_TYPE: str = "int8"

# On-screen text detection (optional OCR)
OCR_SAMPLE_FRAMES: int = 6
OCR_MIN_CONFIDENCE: float = 0.6
OCR_MIN_TEXT_LENGTH: int = 3

# Translation (Claude API)
DEFAULT_TRANSLATION_MODEL: str = "claude-opus-5-5"
DEFAULT_TRANSLATION_EFFORT: str = "medium"
TRANSLATION_MAX_TOKENS: int = 16000
# Characters per second a viewer can read (subtitles) or a TTS voice can speak (dub) comfortably.
SUBTITLE_CHARS_PER_SECOND: float = 17.0
DUB_CHARS_PER_SECOND: float = 14.0
MIN_SEGMENT_CHARS: int = 12
BUDGET_TOLERANCE: float = 1.15

# Subtitles
SUBTITLE_MAX_LINES: int = 2
SUBTITLE_CHAR_WIDTH_RATIO: float = 0.55
SUBTITLE_SIDE_MARGIN_RATIO: float = 0.06

# Dub (TTS)
DUB_MAX_SPEEDUP: float = 1.35
DUB_BACKGROUND_VOLUME: float = 0.12
DUB_SAMPLE_RATE: int = 44100
DEFAULT_TTS_VOICES: Dict[str, str] = {
    "pt": "pt-BR-AntonioNeural",
    "pt-BR": "pt-BR-AntonioNeural",
    "pt-PT": "pt-PT-DuarteNeural",
    "es": "es-MX-JorgeNeural",
    "es-ES": "es-ES-AlvaroNeural",
    "en": "en-US-GuyNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
}
