"""
Live end-to-end check of the localization pipeline against real services.

Runs one real video through download (yt-dlp) -> transcribe (faster-whisper) -> translate (local OPUS-MT) -> voice (local Piper)
-> voice (subtitles, plus edge-tts in dub mode) in an isolated temp database and workspace,
so it never touches data/cache.sqlite3.

Usage:
    python scripts/smoke_live.py --check
    python scripts/smoke_live.py https://www.youtube.com/shorts/<id> --language pt-BR --mode dub

Needs network access only to the video platform and, the first time, to download the local models
(huggingface.co for Whisper and Piper, argos-net.com for translation). No API keys.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HOSTS = {
    "YouTube": "www.youtube.com",
    "Instagram": "www.instagram.com",
    "TikTok": "www.tiktok.com",
    "Whisper models + Piper voices (Hugging Face)": "huggingface.co",
    "Translation model index": "raw.githubusercontent.com",
    "Translation models (Argos)": "argos-net.com",
}


def check_hosts() -> bool:
    import requests

    ok = True

    for label, host in HOSTS.items():
        try:
            requests.head(f"https://{host}", timeout=8, allow_redirects=False)
            print(f"  ok    {label:32} {host}")
        except (requests.RequestException, socket.error) as err:
            ok = False
            print(f"  FAIL  {label:32} {host}  ({type(err).__name__})")

    return ok


def run(url: str, language: str, mode: str, workdir: Path) -> int:
    from underfind.backend.db.pipeline_repo import PipelineRepository
    from underfind.backend.pipeline.runner import PipelineRunner
    from underfind.backend.pipeline.stages import StageContext, Workspace
    from underfind.backend.schemas.pipeline import PageProfile
    from underfind.backend.services.job_service import JobService

    repo = PipelineRepository(db_path=workdir / "smoke.sqlite3")
    page = repo.save_page(PageProfile(
        display_name="Smoke Test",
        handle="smoke_test",
        language=language,
        auto_approve_translation=True,
    ))
    ctx = StageContext(repo=repo, workspace=Workspace(sources_dir=workdir / "sources", jobs_dir=workdir / "jobs"))
    job = JobService(repo).open_job_from_url(url, page_id=page.id, mode=mode, force=True)

    print(f"Job {job.id}: {job.source_key} -> {language} ({mode}); workdir {workdir}")
    job = PipelineRunner(ctx).run_until_blocked(job.id)

    print(f"\nFinal status: {job.status.value}" + (f"  error: {job.error}" if job.error else ""))
    print(json.dumps(job.artifacts, indent=2))

    for event in repo.get_job_events(job.id):
        print(f"  {event.created_at}  {event.from_status.value if event.from_status else '-':12} -> {event.to_status.value:12} {event.note or ''}")

    if "translation" in job.artifacts:
        translation = json.loads(Path(job.artifacts["translation"]).read_text(encoding="utf-8"))
        print("\nCaption:", translation["caption"])
        print("Hashtags:", " ".join(translation["hashtags"]))

        for seg in translation["segments"][:5]:
            print(f"  [{seg['start']:6.2f}] {seg['source_text']}\n           {seg['text']}")

    return 0 if job.status.value == "voiced" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", nargs="?", help="YouTube / Instagram / TikTok video URL")
    parser.add_argument("--language", default="pt-BR", help="Target page language (default pt-BR)")
    parser.add_argument("--mode", choices=["subtitles", "dub"], default="subtitles")
    parser.add_argument("--workdir", type=Path, default=None, help="Keep artifacts here instead of a temp dir")
    parser.add_argument("--check", action="store_true", help="Only check network access to the required hosts")
    args = parser.parse_args()

    if args.check or not args.url:
        print("Network access:")
        return 0 if check_hosts() else 1

    if args.workdir:
        args.workdir.mkdir(parents=True, exist_ok=True)
        return run(args.url, args.language, args.mode, args.workdir)

    with tempfile.TemporaryDirectory(prefix="underfind-smoke-") as tmp:
        return run(args.url, args.language, args.mode, Path(tmp))


if __name__ == "__main__":
    sys.exit(main())
