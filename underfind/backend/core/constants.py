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
