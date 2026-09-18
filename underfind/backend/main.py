from __future__ import annotations

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

load_dotenv()

from underfind.backend.core.constants import (
    SERVICE_NAME,
    SERVICE_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    FRONTEND_DIST_DIR,
)
from underfind.backend.core.logger import logger
from underfind.backend.routers import api_router

app = FastAPI(
    title="Underfind Content Intelligence Engine",
    description="Automated discovery of viral YouTube Shorts outliers, hook dissection (0-3s), and AI creative modeling.",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def serve_home():
    if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
        return FileResponse(FRONTEND_DIST_DIR / "index.html")

    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "message": f"Underfind v{SERVICE_VERSION} API is active.",
        "docs": "/docs",
    }


def start():
    """Starts the Uvicorn server hosting API and compiled React frontend."""
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    host = os.environ.get("HOST", DEFAULT_HOST)

    logger.info("Starting Underfind v%s Engine at http://localhost:%d (API Docs: http://localhost:%d/docs)", SERVICE_VERSION, port, port)
    uvicorn.run("underfind.backend.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    start()
