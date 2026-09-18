# Underfind - AI Agent & Architecture Guidelines (`GEMINI.md`)

## 1. Project Overview & Mission
**Underfind (v2.1)** is a specialized **Content Intelligence & Creative Modeling Engine** designed for video creators, editors, and media agencies. It discovers YouTube Shorts and short-form outliers (videos where small channels break out with massive view counts), dissects the first 3-5 seconds opening hook, extracts time-coded transcripts, models high-converting scripts via AI, and generates cut markers ready for **MedPy** raw footage clipping.

---

## 2. Mandatory SOP & Engineering Rules

### Rule 01: Top-Level Imports Only
- **All imports must strictly reside in the file header.**
- **NEVER** import libraries, modules, or dependencies inside functions, methods, or conditional branches.
- Follow strict PEP 8 grouping:
  1. Standard Library (`os`, `sys`, `json`, `sqlite3`, `datetime`, `pathlib`)
  2. Third-Party (`fastapi`, `pydantic`, `googleapiclient`, `youtube_transcript_api`)
  3. Internal Core (`underfind.backend.core.constants`, `underfind.backend.core.utils`, `underfind.backend.core.logger`)

### Rule 02: Vertical Spacing & Logical Block Separation
- No cramped nested conditional blocks.
- Maintain blank lines between variable declarations, conditional checks (`if cached:`), filters, and returns.
- Logging statements (`logger.info`, `logger.error`) must always sit directly above before the `return` statement.

### Rule 03: Centralized Constants (`underfind/backend/core/constants.py`)
- All thresholds, numbers, default parameters, timeouts, cut markers, and paths must be defined in `underfind/backend/core/constants.py`.
- No magic numbers or hardcoded configuration strings in business logic.

### Rule 04: Centralized Utilities (`underfind/backend/core/utils.py`)
- All parsing, formatting, calculations (`calculate_viral_ratio`), tier classifications, and string sanitization must reside in `underfind/backend/core/utils.py`.

### Rule 05: Multi-Line Parameter Indentation (3+ Parameters)
- Any function definition or method with **3 or more parameters** must break each parameter onto its own line with indentation.
- Any function call with **3 or more arguments** must break each argument onto its own line.

### Rule 06: Private Functions First (Declaration Precedes Usage)
- All private functions and private methods (prefixed with `_`) must be declared at the top of the file or class, BEFORE any public functions and methods.
- Private helpers are established first, followed by public consumer methods below.

### Rule 07: Language Standards
- **English is mandatory** across all source code, docstrings, comments, error messages, API schemas, and frontend UI text.
- The **only** document in Brazilian Portuguese is `README.md`.

### Rule 08: Emil Kowalski UI Craft & Motion
- **Zero emojis anywhere in the UI.** Use crisp Lucide SVG icons.
- Interactive elements must implement active scale physics: `:active { transform: scale(0.97); }`.
- Custom easing curves: `cubic-bezier(0.23, 1, 0.32, 1)`.
- Entrance animations must scale from `scale(0.96); opacity: 0` (never `scale(0)`).
- Provide a `| Before | After | Why |` comparison table in all design engineering reviews.

### Rule 09: Zero-Quota SQLite Cache
- Every query must check `data/cache.sqlite3` first before calling external YouTube APIs to preserve 100% of user API quota.

### Rule 10: Centralized Custom Logger (`underfind/backend/core/logger.py`)
- Never call `logging.basicConfig` or `logging.getLogger` in business logic modules.
- Import singleton: `from underfind.backend.core.logger import logger`.
- Supported levels: `logger.trace`, `logger.debug`, `logger.info`, `logger.warning`, `logger.error`.
- Outgoing API calls and sending parameters: `logger.debug(...)`.
- Incoming API responses, payloads, and counts: `logger.trace(...)`.
- Operational milestones & cache hits: `logger.info(...)`.

### Rule 11: Clean, Minimal Documentation
- No decorative `# ---` or `###` comment banners. Clean, concise, self-documenting code.

### Rule 12: Top-Level Declarations
- Functions, lists, and dicts must sit at the top after imports and logger.
- Mapping dictionaries like `HANDLERS` directly reference declared functions without mutating decorators.

### Rule 13: Modular FastAPI Architecture
- `core/`: Constants, logger, utils.
- `schemas/`: Pydantic request/response schemas.
- `services/`: Business logic services (`YouTubeService`, `TranscriptService`).
- `db/`: Database & cache manager.
- `routers/`: Segmented APIRouters.
- `dependencies.py`: Injected dependencies.
- `main.py`: Entry point and mounting.

---

## 3. Technology Stack & Execution

### Backend
- **Python 3.12+**, **FastAPI**, **Uvicorn**, **Pydantic v2**, **SQLite3**.
- YouTube Data API v3 & YouTube Analytics API with permanent SQLite local persistence.

### Frontend
- **React 18**, **TypeScript**, **Vite**, **Vanilla CSS** with Emil Kowalski design tokens.
- UI views: `DashboardView`, `ShortsOutliersView`, `TrendingView`, `AdvancedSearchView`, `McpView`, and `VideoWorkspaceModal`.

### Execution
- Launch natively via `python app.py` (running on `http://localhost:8000`) or via Docker (`docker compose up --build`).
- Frontend production assets compiled via `npm run build` in `underfind/frontend/` into `underfind/frontend/dist`.

