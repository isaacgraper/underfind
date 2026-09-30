from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, Query

from underfind.backend.core.errors import NotFoundError
from underfind.backend.core.quota import QuotaTracker
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo, get_youtube_quota
from underfind.backend.schemas.pipeline import PageProfile, QuotaStatus, RenderTemplate

router = APIRouter(tags=["Pages, Templates & Quota"])


@router.get("/pages", response_model=List[PageProfile])
def list_pages(
    active_only: bool = Query(False),
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> List[PageProfile]:
    return repo.list_pages(active_only=active_only)


@router.post("/pages", response_model=PageProfile)
def create_page(
    page: PageProfile,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> PageProfile:
    """Creates a target page identity (display name, handle, avatar, language, template)."""
    return repo.save_page(page.model_copy(update={"id": None}))


@router.get("/pages/{page_id}", response_model=PageProfile)
def get_page(
    page_id: int,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> PageProfile:
    page = repo.get_page(page_id)

    if not page:
        raise NotFoundError(f"Page profile {page_id} not found.")

    return page


@router.put("/pages/{page_id}", response_model=PageProfile)
def update_page(
    page_id: int,
    page: PageProfile,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> PageProfile:
    return repo.save_page(page.model_copy(update={"id": page_id}))


@router.delete("/pages/{page_id}")
def delete_page(
    page_id: int,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> dict:
    if not repo.delete_page(page_id):
        raise NotFoundError(f"Page profile {page_id} not found.")

    return {"status": "deleted", "page_id": page_id}


@router.get("/templates", response_model=List[RenderTemplate])
def list_templates(
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> List[RenderTemplate]:
    return repo.list_templates()


@router.post("/templates", response_model=RenderTemplate)
def create_template(
    template: RenderTemplate,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> RenderTemplate:
    """Creates a render template (header layout, fonts, colors, subtitle style) for the profile + video format."""
    return repo.save_template(template.model_copy(update={"id": None}))


@router.put("/templates/{template_id}", response_model=RenderTemplate)
def update_template(
    template_id: int,
    template: RenderTemplate,
    repo: PipelineRepository = Depends(get_pipeline_repo),
) -> RenderTemplate:
    return repo.save_template(template.model_copy(update={"id": template_id}))


@router.get("/quota", response_model=List[QuotaStatus])
def get_quota(
    quota: QuotaTracker = Depends(get_youtube_quota),
) -> List[QuotaStatus]:
    """Today's API unit usage per provider."""
    return [quota.status()]
