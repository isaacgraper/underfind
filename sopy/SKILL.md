---
name: sopy
description: >-
  Standard Operating Procedures for Python (SOPy) - Strict, idiomatic Python & FastAPI
  engineering doctrine: top-level imports, vertical breathing room, multi-line comprehensions,
  centralized constants & utilities, parameter indentation, private-first ordering,
  top declarations, semantic custom logger, and clean modular architecture.
---

# SOPy: Python & FastAPI Engineering Standards

A comprehensive, idiomatic Standard Operating Procedure for high-performance Python and FastAPI projects.

---

## 1. Imports & Namespaces (PEP 8)

* **Top-Level Only:** All imports must strictly reside in the file header. Never import inside functions, methods, or conditional branches.
* **PEP 8 Grouping:**
  1. Standard library (`os`, `sys`, `pathlib`, `json`, `datetime`)
  2. Third-party packages (`fastapi`, `pydantic`, `rich`)
  3. Local / internal core application packages (`core.constants`, `core.utils`, `core.logger`)
* **Modern Typing:** Use Python 3.10+ native typing (`list[str]`, `dict[str, Any]`, `str | None`) combined with `from __future__ import annotations`.

---

## 2. Vertical Spacing & Logical Block Separation

* **Vertical Breathing Room:** No cramped or crowded blocks. Maintain blank lines between variable declarations, conditional checks, transformations, and returns.
* **Pre-Return Logging:** Log statements (`logger.info`, `logger.error`) must sit immediately above before the `return` statement.
* **Example:**
  ```python
  record = query_database(key)

  if record:
      transformed = transform_payload(record)

      logger.info("Transformed %d records successfully.", len(transformed))
      return transformed
  ```

---

## 3. Multi-Line Indented Comprehensions

* Whenever a list, dict, or set comprehension contains an `if` filter clause or multiple iterations, format each clause onto its own indented line:
  ```python
  # List comprehension with filtering condition:
  filtered = [
      item for item in result
      if item.is_valid
  ]

  # Dict comprehension with filtering condition:
  user_map = {
      user.id: user.name
      for user in users
      if user.is_active
  }
  ```
* Never cram filtered comprehensions onto a single run-on line.

---

## 4. Centralized Constants (`core/constants.py`)

* Define all thresholds, magic numbers, defaults, language lists, timeouts, and configuration strings in a single dedicated module.
* Business logic modules must contain zero magic numbers or hardcoded configuration values.

---

## 5. Centralized Utilities (`core/utils.py`)

* Shared helper functions (parsing, string transformations, mathematical calculations, sanitization, tier classification) must reside in a dedicated utilities module.
* Keep utilities pure, stateless, and fully unit-tested.

---

## 6. Multi-Line Parameter Indentation (3+ Rule)

* Signatures with **3 or more parameters** must break each parameter onto its own indented line:
  ```python
  def create_resource(
      name: str,
      target_path: Path,
      is_active: bool,
  ) -> Resource:
      pass
  ```
* Invocations with **3 or more arguments** must break each argument onto its own indented line:
  ```python
  create_resource(
      resource_name,
      resolved_path,
      True,
  )
  ```

---

## 7. Private Functions First (Declaration Precedes Usage)

* All private helpers (prefixed with `_`) must be defined at the top of the file or class before any public methods.
* Establishes internal building blocks before exposing the public API surface below.

---

## 8. Top-Level Declarations

* Functions, lists, and dicts must sit at the top of the module directly after imports and logger initialization.
* Mapping tables (e.g. `HANDLERS: dict[str, Callable]`) must directly reference declared functions without relying on empty mutating dictionaries or runtime registration decorators:
  ```python
  HANDLERS: dict[str, Callable] = {
      "action_one": handle_action_one,
      "action_two": handle_action_two,
  }
  ```

---

## 9. Centralized Custom Logger & Strict Semantics

* Never call `logging.basicConfig()` or `logging.getLogger(__name__)` across application modules.
* Single singleton import: `from core.logger import logger`.
* Supported levels: `logger.trace`, `logger.debug`, `logger.info`, `logger.warning`, `logger.error`.
* `critical` delegates directly to `error` (all critical events are errors).
* **Strict Log Semantics**:
  - `logger.debug(...)`: Outgoing calls, API invocations, and sending parameters.
  - `logger.trace(...)`: Incoming responses, raw payload inspection, and received item counts.
  - `logger.info(...)`: High-level operational milestones and successes.
  - `logger.warning(...)`: Soft errors, retries, and fallback paths.
  - `logger.error(...)`: Unhandled failures and exceptions.
* Output streams strictly to `sys.stderr` with Rich formatting and timestamps, preserving `sys.stdout` for CLI pipes and protocol communication (e.g., MCP JSON-RPC).

---

## 10. Python Idioms & Clean Code

* Prefer `pathlib.Path` over `os.path`.
* Guard clauses and early returns over deeply nested `if/else` structures.
* Context managers (`with ...`) for all file, connection, and lock lifecycles.
* No decorative comment banners (`# ---` or `###`). Code must be concise, expressive, and self-documenting.

---

## 11. Modular Architecture (FastAPI Standards)

* `core/`: Constants, logger, utilities.
* `schemas/`: Pydantic request/response validation models.
* `services/`: Encapsulated domain business logic.
* `db/`: Database clients, sessions, and persistence managers.
* `routers/`: Segmented APIRouter modules.
* `dependencies.py`: Dependency injection providers.
* `main.py`: App initialization, middleware, static asset mounting, and server runner.

---

## 12. Language Standards

* All code, docstrings, variable names, comments, error messages, and schemas must be in **English**.
* The project README may be maintained in the user's native language.

---

## 13. Clean Containerization & Native Runners

* Standard Docker multi-stage builds and Docker Compose.
* Launch natively using `python app.py` (avoid platform-specific `.bat` or `.sh` wrapper scripts).
