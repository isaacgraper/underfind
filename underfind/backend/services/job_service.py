from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, List, Optional

import requests

from underfind.backend.core.constants import DEFAULT_LOCALIZATION_MODE
from underfind.backend.core.errors import SourceAlreadyUsedError
from underfind.backend.core.logger import logger
from underfind.backend.core.utils import parse_source_url, is_tiktok_short_link
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.schemas.pipeline import Job, Platform, SourceVideo
from underfind.backend.schemas.video import VideoItem


def resolve_redirect(url: str) -> str:
    """Follows redirects of share links (vm.tiktok.com, tiktok.com/t/...) to the canonical video URL."""
    res = requests.head(url, allow_redirects=True, timeout=10)
    return res.url


class JobService:
    """Registers source videos and opens localization jobs, enforcing the used-source registry."""

    def __init__(
        self,
        repo: PipelineRepository,
        redirect_resolver: Callable[[str], str] = resolve_redirect,
    ):
        self.repo = repo
        self._resolve = redirect_resolver

    def source_from_url(
        self,
        url: str,
    ) -> SourceVideo:
        clean = url.strip()

        if is_tiktok_short_link(clean):
            resolved = self._resolve(clean)
            logger.debug("Resolved TikTok share link %s -> %s", clean, resolved)
            clean = resolved

        platform, source_id = parse_source_url(clean)
        return SourceVideo(platform=Platform(platform), source_id=source_id, url=clean)

    @staticmethod
    def source_from_video_item(video: VideoItem) -> SourceVideo:
        return SourceVideo(
            platform=Platform.YOUTUBE,
            source_id=video.video_id,
            url=video.video_url or f"https://www.youtube.com/watch?v={video.video_id}",
            title=video.title,
            caption=video.description,
            author_handle=video.channel_id,
            author_name=video.channel_title,
            thumbnail_url=video.thumbnail_url,
            views=video.views,
            likes=video.likes,
            comments_count=video.comments_count,
            followers=video.subscribers,
            duration_seconds=video.duration_seconds,
            published_at=video.published_at,
        )

    def open_job(
        self,
        source: SourceVideo,
        page_id: Optional[int] = None,
        mode: str = DEFAULT_LOCALIZATION_MODE,
        force: bool = False,
        local_only: Optional[bool] = None,
    ) -> Job:
        """
        Creates a job for a source unless it was already used, or is a near-duplicate
        (same perceptual hash) of a used source from any platform. force=True skips the registry.
        """
        if not force:
            existing = self.repo.get_source_job_id(source.key)

            if existing:
                raise SourceAlreadyUsedError(source.key, existing_job_id=existing)

            if source.phash:
                for similar, _distance in self.repo.find_similar_sources(source.phash, exclude_key=source.key):
                    similar_job = self.repo.get_source_job_id(similar.key)

                    if similar_job:
                        raise SourceAlreadyUsedError(source.key, existing_job_id=similar_job, duplicate_of=similar.key)

        stored = self.repo.upsert_source(source)
        return self.repo.create_job(stored.key, page_id=page_id, mode=mode, local_only=local_only)

    def open_job_from_url(
        self,
        url: str,
        page_id: Optional[int] = None,
        mode: str = DEFAULT_LOCALIZATION_MODE,
        force: bool = False,
        local_only: Optional[bool] = None,
    ) -> Job:
        return self.open_job(self.source_from_url(url), page_id=page_id, mode=mode, force=force, local_only=local_only)

    def open_job_from_files(
        self,
        files: List[str],
        source_url: Optional[str] = None,
        caption: Optional[str] = None,
        author_handle: Optional[str] = None,
        page_id: Optional[int] = None,
        mode: str = DEFAULT_LOCALIZATION_MODE,
        force: bool = False,
        local_only: Optional[bool] = None,
    ) -> Job:
        """
        A job from media already on this machine. The source id is a content hash of the files, so the same
        files never make two jobs; a given source_url is also checked against the registry of used posts.
        """
        paths = [Path(f).expanduser().resolve() for f in files]
        missing = [str(p) for p in paths if not p.is_file()]

        if missing:
            raise ValueError(f"Files not found: {missing}")

        digest = hashlib.sha1()

        for path in paths:
            digest.update(path.read_bytes())

        if source_url and not force:
            try:
                linked = self.source_from_url(source_url)
            except ValueError:
                linked = None

            existing = self.repo.get_source_job_id(linked.key) if linked else None

            if existing:
                raise SourceAlreadyUsedError(linked.key, existing_job_id=existing)

        source = SourceVideo(
            platform=Platform.LOCAL,
            source_id=digest.hexdigest()[:16],
            url=source_url or f"local://{paths[0].name}",
            caption=caption,
            author_handle=author_handle,
            media_files=[str(p) for p in paths],
        )
        return self.open_job(source, page_id=page_id, mode=mode, force=force, local_only=local_only)
