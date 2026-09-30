from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

load_dotenv()

from underfind.backend.core.constants import (
    SERVICE_NAME,
    SERVICE_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    FRONTEND_DIST_DIR,
)
from underfind.backend.core.errors import (
    InvalidTransitionError,
    NotFoundError,
    QuotaExceededError,
    SourceAlreadyUsedError,
)
from underfind.backend.core.logger import logger
from underfind.backend.routers import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts the pipeline worker in-process when PIPELINE_WORKER_ENABLED=true."""
    stop_event = threading.Event()
    worker: threading.Thread | None = None

    if os.environ.get("PIPELINE_WORKER_ENABLED", "").lower() in ("1", "true", "yes"):
        from underfind.backend.pipeline.runner import get_default_runner

        worker = threading.Thread(
            target=get_default_runner().run_forever,
            args=(stop_event,),
            name="pipeline-worker",
            daemon=True,
        )
        worker.start()

    yield

    stop_event.set()

    if worker is not None:
        worker.join(timeout=10)


app = FastAPI(
    lifespan=lifespan,
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


@app.exception_handler(QuotaExceededError)
def handle_quota_exceeded(request: Request, exc: QuotaExceededError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc), "provider": exc.provider, "used": exc.used, "limit": exc.limit},
    )


@app.exception_handler(SourceAlreadyUsedError)
def handle_source_used(request: Request, exc: SourceAlreadyUsedError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": str(exc),
            "source_key": exc.source_key,
            "existing_job_id": exc.existing_job_id,
            "duplicate_of": exc.duplicate_of,
        },
    )


@app.exception_handler(InvalidTransitionError)
def handle_invalid_transition(request: Request, exc: InvalidTransitionError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(sqlite3.IntegrityError)
def handle_integrity_error(request: Request, exc: sqlite3.IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": f"Conflicts with an existing record: {exc}"})


@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValueError)
def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})

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
