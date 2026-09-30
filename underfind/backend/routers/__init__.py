from __future__ import annotations

from fastapi import APIRouter

from underfind.backend.routers.search import router as search_router
from underfind.backend.routers.trending import router as trending_router
from underfind.backend.routers.blueprint import router as blueprint_router
from underfind.backend.routers.ideas import router as ideas_router
from underfind.backend.routers.dashboard import router as dashboard_router
from underfind.backend.routers.jobs import router as jobs_router
from underfind.backend.routers.pages import router as pages_router

api_router = APIRouter(prefix="/api")

api_router.include_router(search_router)
api_router.include_router(trending_router)
api_router.include_router(blueprint_router)
api_router.include_router(ideas_router)
api_router.include_router(dashboard_router)
api_router.include_router(jobs_router)
api_router.include_router(pages_router)

__all__ = [
    "api_router",
    "search_router",
    "trending_router",
    "blueprint_router",
    "ideas_router",
    "dashboard_router",
    "jobs_router",
    "pages_router",
]
