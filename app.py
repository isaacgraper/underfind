from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the project root and backend are in python path
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if BACKEND_DIR.exists() and str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from underfind.backend.main import start
from underfind.backend.cli import main as cli_main

if __name__ == "__main__":
    # If subcommands are passed via command line, delegate to Rich CLI
    if len(sys.argv) > 1 and sys.argv[1] in ("search", "trending", "blueprint", "serve", "worker", "run", "models", "add", "approve", "scan", "queue"):
        cli_main()
    else:
        # Default: start the web engine & FastAPI server on http://localhost:8000
        # `python app.py --online` unlocks online AI models; `--local` (or nothing) keeps every model local.
        if "--online" in sys.argv[1:]:
            os.environ["AI_MODE"] = "online"
        elif "--local" in sys.argv[1:]:
            os.environ["AI_MODE"] = "local"

        start()
