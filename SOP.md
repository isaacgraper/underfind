# Standard Operating Procedures (SOP)

## Core Software Engineering & Architecture Standards

### Rule 01: Top-Level Imports Only
- **All module, library, and dependency imports must reside strictly in the file header.**
- **NEVER** import libraries, modules, or dependencies inside functions, methods, or conditional blocks.
- Adhere strictly to PEP 8 import grouping:
  1. Standard library imports (e.g., `os`, `sys`, `json`, `sqlite3`, `datetime`, `pathlib`)
  2. Third-party library imports (e.g., `fastapi`, `pydantic`, `rich`)
  3. Internal core application imports (e.g., constants, utilities, logger)

### Rule 02: Vertical Spacing & Logical Block Separation
- **No cramped or tightly packed code blocks.**
- Maintain clear vertical breathing room (blank lines) between:
  - Variable assignments and conditional checks:
    ```python
    result = retrieve_data(query_key)

    if result:
        filtered = [item for item in result if item.is_valid]

        logger.info("Processed %d valid records.", len(filtered))
        return filtered
    ```
  - Filtering logic, transformations, and return statements.
  - Logging statements (`logger.info`, `logger.error`, etc.) must always sit directly above before the `return` statement.

### Rule 03: Centralized Constants
- **All constants** (thresholds, numbers, default configurations, language lists, paths, and timeouts) must be defined and centralized in a dedicated constants module (`core/constants.py`).
- No magic numbers or hardcoded configuration strings are permitted inside business logic.

### Rule 04: Centralized Utilities & Helper Functions
- **All shared helper and utility functions** (parsing, formatting, calculations, text sanitization, and tier classification) must reside in a dedicated utilities module (`core/utils.py`).

### Rule 05: Multi-Line Parameter Indentation (3+ Parameters)
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

### Rule 06: Private Functions First (Declaration Precedes Usage)
- **All private functions and private methods (prefixed with `_`) must be defined at the top of the file or class, BEFORE any public functions and methods.**
- Helper routines must be established first so that they are readily available to the public interface below.

### Rule 07: Top-Level Declarations (Functions, Lists, and Dictionaries)
- Functions, lists, and dictionaries must reside at the top of the file, directly after imports and logger initialization.
- Mapping dictionaries (e.g., handler dispatch tables) must directly reference declared functions without relying on empty mutating dictionaries or runtime registration decorators:
  ```python
  HANDLERS: Dict[str, Callable] = {
      "action_one": handle_action_one,
      "action_two": handle_action_two,
  }
  ```

### Rule 08: Centralized Custom Logger & Semantic Logging
- Modules must **never** call `logging.basicConfig()` or `logging.getLogger(__name__)`.
- Import the single centralized application logger: `from ...core.logger import logger`.
- Supported levels: `logger.trace`, `logger.debug`, `logger.info`, `logger.warning`, `logger.error`.
- **Critical equals error**: Any critical issue is treated as an error (`logger.critical` delegates to `logger.error`).
- **Log Semantics**:
  - **Outgoing calls / function executions / sending parameters**: `logger.debug(...)`
  - **Incoming responses / payload tracing / received records**: `logger.trace(...)`
  - **Operational milestones & high-level successes**: `logger.info(...)`
  - **Soft warnings, fallbacks, and retries**: `logger.warning(...)`
  - **Failures and exceptions**: `logger.error(...)`
- Console output must stream to `sys.stderr` with clear timestamps and formatted levels, ensuring standard output (`sys.stdout`) remains clean for CLI pipes and protocol communication.

### Rule 09: Clean Code & Minimal Documentation
- No decorative `# ---` or `###` comment banners.
- Code must be concise, expressive, and self-documenting.
- Comments must only explain non-obvious rationale, avoiding redundant restatements of what the code obviously does.

### Rule 10: Modular Project Architecture
Maintain clear, decoupled separation of concerns:
- `core/`: Application settings, constants, logger, and utility functions.
- `schemas/`: Pydantic request and response schemas.
- `services/`: Encapsulated domain business logic.
- `db/`: Database clients, caching, and persistence mechanisms.
- `routers/`: Segmented API endpoint routers.
- `dependencies.py`: Injected dependencies.
- `main.py`: Main application assembly, middleware, and router mounts.

### Rule 11: Language Standards
- **English is mandatory** across all source code, docstrings, comments, error messages, and API schemas.
- Non-English documentation is strictly restricted to the user-facing onboarding README.

### Rule 12: UI Craft & Motion Principles
- Zero emojis anywhere in the interface; use crisp SVG icons.
- Physical active scale on interactive elements (`:active { transform: scale(0.97); }`).
- Motion and transitions must utilize defined cubic-bezier easing curves (`cubic-bezier(0.23, 1, 0.32, 1)`).
- Entrance animations must scale from `scale(0.96); opacity: 0` (never `scale(0)`).

### Rule 13: Clean Containerization & Native Entrypoints
- Use standard Docker / Docker Compose configurations for containerized workflows.
- Run projects directly via native commands (e.g., `python app.py`), avoiding platform-specific startup scripts (no `.bat` or `.sh` wrapper scripts).
