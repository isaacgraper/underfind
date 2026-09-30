from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Dict, Callable, Any
from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from underfind.backend.core.constants import (
    DEFAULT_REGION,
    DEFAULT_MAX_RESULTS,
    VIRAL_THRESHOLD_EXTREME,
    VIRAL_THRESHOLD_OUTLIER,
    VIRAL_THRESHOLD_NEUTRAL,
    SERVICE_VERSION,
)
from underfind.backend.core.logger import logger
from underfind.backend.services.youtube_service import YouTubeService
from underfind.backend.services.transcript_service import TranscriptService
from underfind.backend.schemas.video import SearchRequest, TrendingRequest
from underfind.backend.main import start

console = Console()


def _format_viral_badge(viral_ratio: float) -> str:
    if viral_ratio >= VIRAL_THRESHOLD_EXTREME:
        return f"[bold #10b981]+{viral_ratio:.1f}x VIRAL[/]"

    if viral_ratio >= VIRAL_THRESHOLD_OUTLIER:
        return f"[bold #ff5500]+{viral_ratio:.1f}x OUTLIER[/]"

    if viral_ratio >= VIRAL_THRESHOLD_NEUTRAL:
        return f"[yellow]{viral_ratio:.1f}x[/]"

    return f"[dim]{viral_ratio:.1f}x[/]"


def _render_video_table(
    videos: list,
    title: str,
    out_console: Console,
) -> None:
    table = Table(
        title=f"\n[bold white]{title}[/]",
        box=box.ROUNDED,
        header_style="bold #ff5500",
        border_style="bright_black",
        show_lines=True,
    )

    table.add_column("#", style="dim", width=4, justify="center")
    table.add_column("Title & Channel", style="white", min_width=32)
    table.add_column("Views", justify="right", style="cyan")
    table.add_column("Subscribers", justify="right", style="dim")
    table.add_column("Viral Ratio", justify="right")
    table.add_column("Duration", justify="center", style="dim", width=10)

    for i, v in enumerate(videos, 1):
        ratio_badge = _format_viral_badge(v.viral_ratio)
        dur = f"{v.duration_seconds}s" if v.duration_seconds else "-"
        title_block = f"[bold]{v.title}[/]\n[dim]Channel: {v.channel_title}[/]"

        table.add_row(
            str(i),
            title_block,
            f"{v.views:,}" if v.views else "0",
            f"{v.subscribers:,}" if v.subscribers else "0",
            ratio_badge,
            dur,
        )

    out_console.print(table)


def _render_blueprint_panel(
    bp,
    out_console: Console,
) -> None:
    header = (
        f"[bold white]{bp.title}[/]\n"
        f"[dim]Channel:[/] [cyan]{bp.channel_title}[/] | "
        f"[dim]Views:[/] [cyan]{bp.views:,}[/] | "
        f"[dim]Viral Multiplier:[/] {_format_viral_badge(bp.viral_ratio)}"
    )

    hook_content = (
        f"[bold #ff5500]FIRST {bp.hook_duration:.1f} SECONDS OPENING HOOK:[/]\n\n"
        f"[italic white]\"{bp.hook_text}\"[/]"
    )

    prompt_content = (
        f"[bold #10b981]CALIBRATED SCRIPT MODELING PROMPT:[/]\n\n"
        f"[dim white]{bp.suggested_prompt}[/]"
    )

    out_console.print(Panel(header, title="[bold #ff5500]Underfind Creative Blueprint[/]", border_style="#ff5500"))
    out_console.print(Panel(hook_content, title="[bold yellow]Hook Deconstruction[/]", border_style="yellow"))
    out_console.print(Panel(prompt_content, title="[bold green]AI Script Model[/]", border_style="green"))


def cmd_search(args: argparse.Namespace) -> None:
    logger.debug("Running CLI search with query='%s', region='%s'", args.query, args.region)
    svc = YouTubeService()
    req = SearchRequest(
        query=f"{args.query} #shorts" if args.shorts else args.query,
        is_shorts_only=args.shorts,
        min_views=args.min_views,
        max_subscribers=args.max_subs,
        min_viral_ratio=args.viral_ratio,
        region_code=args.region,
        max_results=args.limit,
    )

    console.print(f"[dim]Searching[/] [bold #ff5500]'{args.query}'[/] [dim](Region: {args.region}, Shorts={args.shorts})...[/]")
    videos = svc.search(req)

    if not videos:
        console.print("[yellow]No videos found matching the specified filters.[/]")
        return

    if args.json:
        console.print(json.dumps([v.model_dump() for v in videos], indent=2, ensure_ascii=False))
        return

    _render_video_table(
        videos,
        f"Outlier Creatives Discovery: '{args.query}'",
        console,
    )
    logger.trace("CLI search completed, %d results displayed", len(videos))


def cmd_trending(args: argparse.Namespace) -> None:
    logger.debug("Running CLI trending for region='%s'", args.region)
    svc = YouTubeService()
    req = TrendingRequest(
        region_code=args.region,
        category_id=args.category,
        shorts_only=args.shorts,
        max_results=args.limit,
    )

    console.print(f"[dim]Fetching trending creatives for region[/] [bold cyan]{args.region}[/]...")
    videos = svc.get_trending(req)

    if not videos:
        console.print("[yellow]No trending videos found.[/]")
        return

    if args.json:
        console.print(json.dumps([v.model_dump() for v in videos], indent=2, ensure_ascii=False))
        return

    _render_video_table(
        videos,
        f"Trending Creatives ({args.region})",
        console,
    )
    logger.trace("CLI trending completed, %d results displayed", len(videos))


def cmd_blueprint(args: argparse.Namespace) -> None:
    logger.debug("Running CLI blueprint for video_id='%s'", args.video_id)
    svc = YouTubeService()
    console.print(f"[dim]Extracting transcript and modeling blueprint for video ID:[/] [bold #ff5500]{args.video_id}[/]...")
    video = svc.get_video_by_id(args.video_id)

    if not video:
        console.print(f"[red]Video '{args.video_id}' not found.[/]")
        return

    blueprint = TranscriptService.create_blueprint(video, custom_niche=args.niche)

    if args.json:
        console.print(json.dumps(blueprint.model_dump(), indent=2, ensure_ascii=False))
        return

    _render_blueprint_panel(blueprint, console)
    logger.trace("CLI blueprint rendered successfully")


def cmd_serve(args: argparse.Namespace) -> None:
    console.print(f"[bold #ff5500]Starting Underfind v{SERVICE_VERSION} API & Web Engine...[/]")
    start()


def cmd_worker(args: argparse.Namespace) -> None:
    import threading
    from underfind.backend.pipeline.runner import get_default_runner

    console.print("[bold #ff5500]Pipeline worker running. Ctrl+C to stop.[/]")
    stop_event = threading.Event()

    try:
        get_default_runner().run_forever(stop_event, interval=args.interval)
    except KeyboardInterrupt:
        stop_event.set()


def cmd_run(args: argparse.Namespace) -> None:
    from underfind.backend.pipeline.runner import get_default_runner

    from underfind.backend.core.errors import NotFoundError

    runner = get_default_runner()

    try:
        job = runner.run_until_blocked(args.job_id) if not args.once else runner.run_next(args.job_id)
    except NotFoundError as err:
        console.print(f"[bold #ef4444]{err}[/]")
        sys.exit(1)

    style = "#10b981" if job.status.value not in ("failed", "discarded") else "#ef4444"
    console.print(f"Job [bold]{job.id}[/] -> [bold {style}]{job.status.value}[/]" + (f"  {job.error}" if job.error else ""))


def cmd_models(args: argparse.Namespace) -> None:
    """Pre-downloads local translation models and Piper voices so the pipeline runs fully offline afterwards."""
    from underfind.backend.pipeline.dub import PiperTtsProvider
    from underfind.backend.pipeline.local_translate import ModelStore

    store = ModelStore(auto_download=True)

    for pair in args.translate or []:
        source, _, target = pair.partition(":")
        path = store.pair_dir(source, target) if store.pair_dir(source, target).exists() else store.download(source, target)
        console.print(f"[#10b981]translation[/] {source}->{target}: {path}")

    voices = PiperTtsProvider(auto_download=True)

    for name in args.voice or []:
        console.print(f"[#10b981]voice[/] {name}: {voices.ensure_voice(name)}")


DISPATCH: Dict[str, Callable[[argparse.Namespace], None]] = {
    "search": cmd_search,
    "trending": cmd_trending,
    "blueprint": cmd_blueprint,
    "serve": cmd_serve,
    "worker": cmd_worker,
    "run": cmd_run,
    "models": cmd_models,
}


def main():
    parser = argparse.ArgumentParser(
        prog="underfind",
        description=f"Underfind v{SERVICE_VERSION} CLI - Content Intelligence & Viral Shorts Engine",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    p_search = subparsers.add_parser("search", help="Search videos or Shorts on YouTube")
    p_search.add_argument("query", help="Search query or niche")
    p_search.add_argument("--shorts", action="store_true", default=False, help="Filter Shorts only")
    p_search.add_argument("--min-views", type=int, default=None, help="Minimum views")
    p_search.add_argument("--max-subs", type=int, default=None, help="Maximum channel subscribers")
    p_search.add_argument("--viral-ratio", type=float, default=None, help="Minimum viral ratio")
    p_search.add_argument("--region", default=DEFAULT_REGION, help=f"Region code (default: {DEFAULT_REGION})")
    p_search.add_argument("--limit", type=int, default=DEFAULT_MAX_RESULTS, help=f"Results limit (default: {DEFAULT_MAX_RESULTS})")
    p_search.add_argument("--json", action="store_true", help="Output JSON format")

    p_trending = subparsers.add_parser("trending", help="Fetch trending videos")
    p_trending.add_argument("--region", default=DEFAULT_REGION, help=f"Region code (default: {DEFAULT_REGION})")
    p_trending.add_argument("--category", default=None, help="Category ID")
    p_trending.add_argument("--no-shorts", dest="shorts", action="store_false", default=True, help="Include long-form")
    p_trending.add_argument("--limit", type=int, default=DEFAULT_MAX_RESULTS, help=f"Results limit (default: {DEFAULT_MAX_RESULTS})")
    p_trending.add_argument("--json", action="store_true", help="Output JSON format")

    p_bp = subparsers.add_parser("blueprint", help="Extract transcript and hook blueprint")
    p_bp.add_argument("video_id", help="YouTube Video ID")
    p_bp.add_argument("--niche", default=None, help="Target creator niche")
    p_bp.add_argument("--json", action="store_true", help="Output JSON format")

    subparsers.add_parser("serve", help="Start the FastAPI backend server")

    p_worker = subparsers.add_parser("worker", help="Run the localization pipeline worker (polls and advances jobs)")
    p_worker.add_argument("--interval", type=float, default=None, help="Seconds between polls")

    p_run = subparsers.add_parser("run", help="Advance one localization job through its automated stages")
    p_run.add_argument("job_id", help="Job ID")
    p_run.add_argument("--once", action="store_true", help="Run only the next stage")

    p_models = subparsers.add_parser("models", help="Download local translation models and Piper voices for offline use")
    p_models.add_argument("--translate", nargs="*", metavar="FROM:TO", help="Language pairs, e.g. en:pb es:en en:es")
    p_models.add_argument("--voice", nargs="*", metavar="NAME", help="Piper voices, e.g. pt_BR-faber-medium es_MX-ald-medium")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command in DISPATCH:
        DISPATCH[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
