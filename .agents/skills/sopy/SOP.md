# SOPy: Python & FastAPI Engineering Standards

## Core Software Engineering & Architecture Standards

### Rule 01: Top-Level Imports Only
- **All module, library, and dependency imports must reside strictly in the file header.**
- **NEVER** import libraries, modules, or dependencies inside functions, methods, or conditional blocks.
- Adhere strictly to PEP 8 import grouping:
  1. Standard library imports (e.g., `os`, `sys`, `json`, `sqlite3`, `datetime`, `pathlib`)
  2. Third-party library imports (e.g., `fastapi`, `pydantic`, `rich`, `openai`, etc.)
  3. Internal core application imports (e.g., constants, utilities, logger)

### Rule 02: Vertical Spacing & Logical Block Separation
- **No cramped or tightly packed code blocks.**
- Maintain clear vertical breathing room (blank lines) between:
  - Variable assignments and conditional checks:
    ```python
    result = retrieve_data(query_key)

    if result:
        filtered = [
            item for item in result
            if item.is_valid
        ]

        logger.info("Processed %d valid records.", len(filtered))
        
        return filtered
    ```
  - Filtering logic, transformations, and return statements.
  - Logging statements (`logger.info`, `logger.error`, etc.) must always sit directly above before the `return` statement.

### Rule 03: Multi-Line Indented Comprehensions
- Whenever a list, dict, or set comprehension contains an `if` filter clause or multiple iterations, format it across multiple indented lines:
  ```python
  filtered = [
      item for item in result
      if item.is_valid
  ]

  mapped_dict = {
      item.id: item.value
      for item in items
      if item.is_active
  }
  ```
- Never write complex or filtered comprehensions on a single crowded line.

### Rule 04: Centralized Constants
- **All constants** (thresholds, numbers, default configurations, language lists, paths, and timeouts) must be defined and centralized in a dedicated constants module (`core/constants.py`).
- No magic numbers or hardcoded configuration strings are permitted inside business logic.

### Rule 05: Centralized Utilities & Helper Functions
- **All shared helper and utility functions** (parsing, formatting, calculations, text sanitization, and tier classification) must reside in a dedicated utilities module (`core/utils.py`).

### Rule 06: Multi-Line Parameter Indentation (3+ Parameters)
- When a function or method signature accepts **3 or more parameters**, break each parameter onto its own indented line:
  ```python
  def execute_task(
      primary_param: str,
      secondary_param: int,
      flag: bool,
  ) -> None:
      pass
  ```
- When calling a function or method with **3 or more arguments**, break each argument onto its own indented line:
  ```python
  execute_task(
      first_value,
      second_value,
      is_enabled,
  )
  ```

### Rule 07: Private Functions First (Declaration Precedes Usage)
- **All private functions and private methods (prefixed with `_`) must be defined at the top of the file or class, BEFORE any public functions and methods.**
- Helper routines must be established first so that they are readily available to the public interface below.

### Rule 08: Top-Level Declarations (Functions, Lists, and Dictionaries)
- Functions, lists, and dictionaries must reside at the top of the file, directly after imports and logger initialization.
- Mapping dictionaries (e.g., handler dispatch tables) must directly reference declared functions without relying on empty mutating dictionaries or runtime registration decorators:
  ```python
  HANDLERS: dict[str, Callable] = {
      "action_one": handle_action_one,
      "action_two": handle_action_two,
  }
  ```

### Rule 09: Centralized Custom Logger & Semantic Logging
- Modules must **never** call `logging.basicConfig()` or `logging.getLogger(__name__)`.
- Import the single centralized application logger: `from core.logger import logger`.
- Supported levels: `logger.trace`, `logger.debug`, `logger.info`, `logger.warning`, `logger.error`.
- **Critical equals error**: Any critical issue is treated as an error (`logger.critical` delegates to `logger.error`).
- **Log Semantics**:
  - **Outgoing calls / function executions / sending parameters**: `logger.debug(...)`
  - **Incoming responses / payload tracing / received records**: `logger.trace(...)`
  - **Operational milestones & high-level successes**: `logger.info(...)`
  - **Soft warnings, fallbacks, and retries**: `logger.warning(...)`
  - **Failures and exceptions**: `logger.error(...)`
- Console output must stream to `sys.stderr` with clear timestamps and formatted levels, ensuring standard output (`sys.stdout`) remains clean for CLI pipes and protocol communication.

### Rule 10: Python Idioms & Clean Code
- Prefer `pathlib.Path` over `os.path`.
- Use modern type hinting (`str | None`, `list[str]`, `dict[str, Any]`) via `from __future__ import annotations`.
- Guard clauses and early returns over deeply nested `if/else` structures.
- Context managers (`with ...`) for file and database sessions.
- No decorative `# ---` or `###` comment banners. Code must be concise, expressive, and self-documenting.

### Rule 11: Modular Project Architecture
Maintain clear, decoupled separation of concerns:
- `core/`: Application settings, constants, logger, and utility functions.
- `schemas/`: Pydantic request and response schemas.
- `services/`: Encapsulated domain business logic.
- `db/`: Database clients, caching, and persistence mechanisms.
- `routers/`: Segmented API endpoint routers.
- `dependencies.py`: Injected dependencies.
- `main.py`: Main application assembly, middleware, and router mounts.

### Rule 12: Language Standards
- **English is mandatory** across all source code, docstrings, comments, error messages, and API schemas.
- Non-English documentation is strictly restricted to the user-facing onboarding README.

### Rule 13: UI Craft & Motion Principles
- Zero emojis anywhere in the interface; use crisp SVG icons.
- Physical active scale on interactive elements (`:active { transform: scale(0.97); }`).
- Motion and transitions must utilize defined cubic-bezier easing curves (`cubic-bezier(0.23, 1, 0.32, 1)`).
- Entrance animations must scale from `scale(0.96); opacity: 0` (never `scale(0)`).

### Rule 14: Clean Containerization & Native Entrypoints
- Use standard Docker / Docker Compose configurations for containerized workflows.
- Run projects directly via native commands (e.g., `python app.py`), avoiding platform-specific startup scripts (no `.bat` or `.sh` wrapper scripts).
