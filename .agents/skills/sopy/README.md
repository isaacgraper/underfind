# SOPy: Python & Engineering Standards

A comprehensive, idiomatic Standard Operating Procedure (SOP) skill for high-performance Python projects.

## Overview

**SOPy** establishes a strict, clean, and maintainable engineering doctrine for Python and projects. It eliminates common architectural pitfalls through 13 non-negotiable rules:

1. **Top-Level Imports Only (PEP 8)** - Grouped and strictly header-level.
2. **Vertical Spacing & Logical Block Separation** - Respiration and pre-return logging.
3. **Multi-Line Indented Comprehensions** - Structured line breaks for filtered comprehensions.
4. **Centralized Constants (`core/constants.py`)** - Zero magic numbers.
5. **Centralized Utilities (`core/utils.py`)** - Pure, stateless helper functions.
6. **Multi-Line Parameter Indentation (3+ Rule)** - Parameters and arguments broken onto indented lines.
7. **Private Functions First** - Declaration precedes usage.
8. **Top-Level Declarations** - Functions, lists, and dicts declared at the top.
9. **Centralized Custom Logger & Semantic Logging** - `trace`, `debug`, `info`, `warning`, `error` over `stderr`.
10. **Python Idioms & Clean Code** - `pathlib.Path`, guard clauses, context managers, and no `# ---` comment banners.
11. **Modular Architecture** - Standard layout (`core/`, `schemas/`, `services/`, `db/`, `routers/`, `dependencies.py`, `main.py`).
12. **Language Standards** - English everywhere in source code, schemas, and docstrings.
13. **Clean Containerization & Native Runners** - Docker / Docker Compose and direct `python app.py` execution.

## Usage as an Antigravity Skill

Place this directory in your project's `.agents/skills/sopy/` or global customization root `~/.gemini/config/skills/sopy/`.

The agent will automatically adhere to SOPy standards whenever designing, generating, refactoring, or reviewing Python and codebases.
