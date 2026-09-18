---
name: python-fastapi-sop
description: >-
  Standard Operating Procedures (SOP) and architectural guidelines for Python and FastAPI projects.
  Use when creating, refactoring, structuring, or reviewing Python/FastAPI codebases according to
  strict personal engineering standards (top-level imports, vertical breathing room, centralized
  constants and utilities, multi-line indentation, private functions first, top declarations,
  custom semantic logger, and modular architecture).
---

# Python & FastAPI Standard Operating Procedures (SOP)

This skill provides the mandatory engineering doctrine, code style standards, and architectural conventions for all Python and FastAPI projects.

---

## 1. Code Style & Organization Rules

### Rule 01: Top-Level Imports Only
* **All imports must strictly reside in the file header.**
* **NEVER** import libraries, modules, or dependencies inside functions, methods, or conditional branches.
* Group imports strictly according to PEP 8:
  1. Standard library (`os`, `sys`, `json`, `sqlite3`, `datetime`, `pathlib`)
  2. Third-party dependencies (`fastapi`, `pydantic`, `rich`)
  3. Internal core application modules (`core.constants`, `core.utils`, `core.logger`)

### Rule 02: Vertical Spacing & Logical Block Separation
* **No cramped or crowded code blocks.**
* Maintain blank lines between:
  - Variable assignments and conditional checks:
    ```python
    record = query_database(key)

    if record:
        transformed = transform_payload(record)

        logger.info("Transformed %d records successfully.", len(transformed))
        return transformed
    ```
  - Filtering operations, transformations, and returns.
  - Logging statements (`logger.info`, `logger.error`, etc.) must always sit directly above before the `return` statement.

### Rule 03: Centralized Constants (`core/constants.py`)
* **All constants** (thresholds, default numbers, paths, configurations, language codes, timeouts) must reside in a centralized constants file.
* Zero magic numbers or hardcoded configuration strings in business logic.

### Rule 04: Centralized Utilities & Helpers (`core/utils.py`)
* **All shared helper and utility functions** (parsing, formatting, calculations, text sanitization, tier classification) must reside in a centralized utilities file.

### Rule 05: Multi-Line Parameter Indentation (3+ Parameters)
* When a function or method signature accepts **3 or more parameters**, break each parameter onto its own line with indentation:
  ```python
  def process_transaction(
      account_id: str,
      amount: float,
      currency: str,
  ) -> TransactionResult:
      pass
  ```
* When calling a function or method with **3 or more arguments**, break each argument onto its own line:
  ```python
  process_transaction(
      user_id,
      payment_amount,
      currency_code,
  )
  ```

### Rule 06: Private Functions First (Declaration Precedes Usage)
* **All private functions and private methods (prefixed with `_`) must be defined at the top of the file or class, BEFORE any public functions and methods.**
* Private helpers are established first, followed by public consumer methods below.

### Rule 07: Top-Level Declarations (Functions, Lists, and Dictionaries)
* Functions, lists, and dictionaries must reside at the top of the file, directly after imports and logger initialization.
* Mapping dictionaries (such as handler dispatch tables) must directly reference declared functions without relying on empty mutating dictionaries or runtime registration decorators:
  ```python
  HANDLERS: Dict[str, Callable] = {
      "action_one": handle_action_one,
      "action_two": handle_action_two,
  }
  ```

---

## 2. Centralized Custom Logger & Semantic Logging

### Rule 08: Logger Implementation & Semantics
* Never call `logging.basicConfig()` or `logging.getLogger(__name__)` across application modules.
* Import a single centralized application logger: `from core.logger import logger`.
* Supported levels: `logger.trace`, `logger.debug`, `logger.info`, `logger.warning`, `logger.error`.
* **Critical equals error**: Any critical issue is treated as an error (`logger.critical` delegates to `logger.error`).
* **Strict Log Semantics**:
  - **Outgoing calls / function executions / sending parameters**: `logger.debug(...)`
  - **Incoming responses / payload tracing / received records**: `logger.trace(...)`
  - **Operational milestones & high-level successes**: `logger.info(...)`
  - **Soft warnings, fallbacks, and retries**: `logger.warning(...)`
  - **Failures and exceptions**: `logger.error(...)`
* Console output must stream to `sys.stderr` with clear timestamps and formatted levels, ensuring standard output (`sys.stdout`) remains clean for CLI pipes and protocol communication.

---

## 3. Documentation & Code Cleanliness

### Rule 09: Clean Code & Minimal Documentation
* No decorative `# ---` or `###` comment banners.
* Code must be concise, expressive, and self-documenting.
* Comments must explain only non-obvious business rationale, avoiding redundant restatements of what the code obviously does.

---

## 4. Modular Project Architecture (FastAPI Standards)

### Rule 10: Standard Modular Directory Layout
Maintain a clean separation of concerns:
```
project/
├── core/
│   ├── constants.py       # Centralized constants, thresholds, paths, timeouts
│   ├── logger.py          # Centralized custom logger with TRACE, DEBUG, stderr handler
│   └── utils.py           # Shared helper functions, parsers, calculations
├── schemas/
│   ├── __init__.py        # Re-exporting schemas
│   ├── domain_a.py        # Domain-specific Pydantic models & request schemas
│   └── domain_b.py        # Domain-specific response & event schemas
├── services/
│   ├── __init__.py        # Re-exporting service classes
│   ├── service_a.py       # Business logic service client A
│   └── service_b.py       # Business logic service client B
├── db/
│   ├── __init__.py
│   └── database.py        # Database engine, sessions, persistent cache managers
├── routers/
│   ├── __init__.py        # Aggregated api_router mounting child routers
│   ├── router_a.py        # Segmented APIRouter endpoints A
│   └── router_b.py        # Segmented APIRouter endpoints B
├── dependencies.py        # Shared FastAPI dependency injection providers
├── main.py                # FastAPI entry point: CORS, middleware, static files, server runner
├── cli.py                 # Terminal interface (if applicable)
├── Dockerfile             # Multi-stage production container build
├── docker-compose.yml     # Container orchestration
└── app.py                 # Root application launcher
```

---

## 5. Global Standards

### Rule 11: Language Standards
* **English is mandatory** across all source code, docstrings, comments, error messages, variable names, and API schemas.
* Non-English text is strictly restricted to the user-facing onboarding README.

### Rule 12: UI Craft & Motion Principles
* Zero emojis anywhere in the interface; use crisp SVG icons.
* Physical active scale on interactive elements: `:active { transform: scale(0.97); }`.
* Motion and transitions must utilize defined cubic-bezier easing curves: `cubic-bezier(0.23, 1, 0.32, 1)`.
* Entrance animations must scale from `scale(0.96); opacity: 0` (never `scale(0)`).

### Rule 13: Clean Containerization & Native Entrypoints
* Use standard Docker / Docker Compose configurations for containerized workflows.
* Run projects directly via native commands (e.g., `python app.py`), avoiding platform-specific startup scripts (no `.bat` or `.sh` wrapper scripts).
