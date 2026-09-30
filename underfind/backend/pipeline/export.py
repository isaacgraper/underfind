from __future__ import annotations

import csv
import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

from underfind.backend.core.constants import EXPORT_SCHEMA_VERSION, EXPORT_WEBHOOK_TIMEOUT_SECONDS, EXPORTS_DIR
from underfind.backend.core.logger import logger
from underfind.backend.schemas.pipeline import (
    ExportDeliverable,
    ExportManifest,
    Job,
    PageProfile,
    SourceVideo,
    Translation,
)

INDEX_FILE = "exports.csv"
INDEX_COLUMNS = ["exported_at", "job_id", "page", "deliverables", "folder", "caption_first_line", "source_url"]
_index_lock = threading.Lock()


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def compose_caption(translation: Translation, page: PageProfile, source: Optional[SourceVideo]) -> str:
    """Localized caption, then the page footer (with credit placeholders filled), then the hashtags."""
    values = _SafeDict(
        source_author=f"@{source.author_handle.lstrip('@')}" if source and source.author_handle else "",
        source_url=source.url if source and not source.url.startswith("local://") else "",
        platform=source.platform.value if source else "",
    )
    footer = (page.caption_footer or "").format_map(values).strip()
    parts = [translation.caption.strip(), footer, " ".join(translation.hashtags).strip()]
    return "\n\n".join(p for p in parts if p)


def _deliverables(artifacts: Dict[str, str]) -> List[tuple[str, List[Path]]]:
    found: List[tuple[str, List[Path]]] = []

    if artifacts.get("reel"):
        found.append(("reel", [Path(artifacts["reel"])]))

    if artifacts.get("post"):
        found.append(("post", [Path(artifacts["post"])]))

    slides = sorted(k for k in artifacts if re.fullmatch(r"carousel_\d+", k))

    if slides:
        found.append(("carousel", [Path(artifacts[k]) for k in slides]))

    return found


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-") or "page"


class FolderExporter:
    """
    Writes one folder per job under <root>/<page handle>/<timestamp>_<job id>/ with the rendered files, caption.txt
    and manifest.json, then appends a row to <root>/exports.csv. The folder is built under a hidden temp name and
    renamed at the end, so a publisher watching the directory never sees a half-written export.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or os.environ.get("EXPORT_DIR") or EXPORTS_DIR)

    def export(
        self,
        job: Job,
        page: PageProfile,
        translation: Translation,
        duration_seconds: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> ExportManifest:
        deliverables = _deliverables(job.artifacts)

        if not deliverables:
            raise FileNotFoundError(f"Job {job.id} has no rendered outputs to export.")

        missing = [str(p) for _, files in deliverables for p in files if not p.exists()]

        if missing:
            raise FileNotFoundError(f"Rendered files missing: {missing}")

        stamp = (now or datetime.now(timezone.utc))
        page_dir = self.root / _slug(page.handle)
        final_dir = page_dir / f"{stamp.strftime('%Y%m%d-%H%M%S')}_{job.id}"
        temp_dir = page_dir / f".tmp_{job.id}_{uuid.uuid4().hex[:6]}"
        temp_dir.mkdir(parents=True)

        try:
            out: List[ExportDeliverable] = []

            for kind, files in deliverables:
                names = []

                for i, path in enumerate(files, start=1):
                    name = f"{kind}{path.suffix}" if len(files) == 1 else f"{kind}_{i:02d}{path.suffix}"
                    shutil.copyfile(path, temp_dir / name)
                    names.append(name)

                out.append(ExportDeliverable(kind=kind, files=names))

            caption = compose_caption(translation, page, job.source)
            source = job.source
            manifest = ExportManifest(
                schema_version=EXPORT_SCHEMA_VERSION,
                job_id=job.id,
                exported_at=stamp.isoformat(),
                folder=str(final_dir),
                page={"handle": page.handle, "display_name": page.display_name, "language": page.language},
                language=page.language,
                deliverables=out,
                caption=caption,
                caption_body=translation.caption,
                hashtags=translation.hashtags,
                headline=translation.headline.replace("*", ""),
                duration_seconds=duration_seconds,
                local_ai=translation.local,
                source={
                    "platform": source.platform.value if source else None,
                    "url": source.url if source else None,
                    "author": source.author_handle if source else None,
                    "published_at": source.published_at if source else None,
                },
                source_metrics={
                    "views": source.views if source else None,
                    "likes": source.likes if source else None,
                    "comments": source.comments_count if source else None,
                    "followers": source.followers if source else None,
                },
            )
            (temp_dir / "caption.txt").write_text(caption + "\n", encoding="utf-8")
            (temp_dir / "manifest.json").write_text(json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
            temp_dir.rename(final_dir)
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

        self._append_index(manifest)
        logger.info("Exported job %s to %s", job.id, final_dir)
        return manifest

    def _append_index(self, manifest: ExportManifest) -> None:
        index = self.root / INDEX_FILE

        with _index_lock:
            new_file = not index.exists()

            with index.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)

                if new_file:
                    writer.writerow(INDEX_COLUMNS)

                writer.writerow([
                    manifest.exported_at,
                    manifest.job_id,
                    manifest.page["handle"],
                    "+".join(d.kind for d in manifest.deliverables),
                    manifest.folder,
                    manifest.caption_body.splitlines()[0] if manifest.caption_body else "",
                    manifest.source.get("url") or "",
                ])

    def list_exports(self, limit: int = 50) -> List[ExportManifest]:
        """Most recent exports first (reads the manifests, so moved or deleted folders drop out)."""
        manifests = sorted(self.root.glob("*/*/manifest.json"), key=lambda p: p.parent.name, reverse=True)
        return [ExportManifest.model_validate_json(p.read_text(encoding="utf-8")) for p in manifests[:limit]]


class WebhookNotifier:
    """Optional: POSTs each manifest to EXPORT_WEBHOOK_URL (e.g. the publisher's API or an n8n webhook)."""

    def __init__(
        self,
        url: Optional[str] = None,
        post: Callable[..., requests.Response] = requests.post,
    ):
        self.url = url if url is not None else (os.environ.get("EXPORT_WEBHOOK_URL") or None)
        self._post = post

    def notify(self, manifest: ExportManifest) -> None:
        if not self.url:
            return

        response = self._post(self.url, json=manifest.model_dump(), timeout=EXPORT_WEBHOOK_TIMEOUT_SECONDS)

        if response.status_code >= 400:
            raise RuntimeError(f"Export webhook returned HTTP {response.status_code}: {response.text[:200]}")
