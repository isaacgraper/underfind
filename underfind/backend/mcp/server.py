from __future__ import annotations

import json
import sys
from typing import Dict, Any, List, Callable
from dotenv import load_dotenv

load_dotenv()

from underfind.backend.core.constants import (
    DEFAULT_REGION,
    DEFAULT_MIN_VIEWS,
    DEFAULT_MAX_SUBSCRIBERS,
    DEFAULT_MIN_VIRAL_RATIO,
    DEFAULT_MCP_MAX_RESULTS,
    DEFAULT_MODELING_TONE,
    DEFAULT_MEDPY_CUT_MARKERS,
    SERVICE_VERSION,
)
from underfind.backend.core.logger import logger
from underfind.backend.core.youtube import YouTubeService
from underfind.backend.core.transcript import TranscriptService
from underfind.backend.core.models import SearchRequest, TrendingRequest, ModelingPromptRequest
from underfind.backend.core.cache import cache_manager


def _send_response(
    response: Dict[str, Any],
) -> None:
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _send_error(
    req_id: Any,
    code: int,
    message: str,
) -> None:
    _send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": code,
            "message": message,
        },
    })


def _format_video_summary(
    v: Any,
) -> Dict[str, Any]:
    return {
        "video_id": v.video_id,
        "title": v.title,
        "channel_title": v.channel_title,
        "views": v.views,
        "subscribers": v.subscribers,
        "viral_ratio": f"{v.viral_ratio}x",
        "duration_seconds": v.duration_seconds,
        "url": v.video_url,
    }


def handle_search_shorts_outliers(
    args: Dict[str, Any],
) -> str:
    logger.debug("Executing search_shorts_outliers with args: %s", args)
    svc = YouTubeService()
    req = SearchRequest(
        query=f"{args['query']} #shorts",
        is_shorts_only=True,
        max_subscribers=args.get("max_subscribers", DEFAULT_MAX_SUBSCRIBERS),
        min_views=args.get("min_views", DEFAULT_MIN_VIEWS),
        min_viral_ratio=args.get("min_viral_ratio", DEFAULT_MIN_VIRAL_RATIO),
        region_code=args.get("region_code", DEFAULT_REGION),
        max_results=args.get("max_results", DEFAULT_MCP_MAX_RESULTS),
        order="viewCount",
    )
    videos = svc.search(req)
    results = [_format_video_summary(v) for v in videos]
    payload = json.dumps(results, indent=2, ensure_ascii=False)

    logger.trace("search_shorts_outliers returned %d items", len(results))
    return payload


def handle_get_video_blueprint(
    args: Dict[str, Any],
) -> str:
    video_id = args["video_id"]
    target_niche = args.get("target_niche")
    logger.debug("Executing get_video_blueprint for video_id='%s', niche='%s'", video_id, target_niche)

    cached_bp = cache_manager.get_cached_blueprint(video_id)
    if cached_bp:
        logger.trace("Returning cached blueprint for video %s", video_id)
        return json.dumps(cached_bp.model_dump(), indent=2, ensure_ascii=False)

    svc = YouTubeService()
    video = svc.get_video_by_id(video_id)
    if not video:
        logger.warning("Video ID '%s' not found for blueprint", video_id)
        return json.dumps({"error": f"Video '{video_id}' not found."}, ensure_ascii=False)

    bp = TranscriptService.create_blueprint(video, custom_niche=target_niche)
    cache_manager.save_blueprint(bp)
    payload = json.dumps(bp.model_dump(), indent=2, ensure_ascii=False)

    logger.trace("Generated blueprint for video %s (length: %d chars)", video_id, len(payload))
    return payload


def handle_get_trending_creatives(
    args: Dict[str, Any],
) -> str:
    region = args.get("region_code", DEFAULT_REGION)
    max_results = args.get("max_results", DEFAULT_MCP_MAX_RESULTS)
    logger.debug("Executing get_trending_creatives for region='%s', max_results=%d", region, max_results)

    svc = YouTubeService()
    req = TrendingRequest(
        region_code=region,
        shorts_only=True,
        max_results=max_results,
    )
    videos = svc.get_trending(req)
    results = [_format_video_summary(v) for v in videos]
    payload = json.dumps(results, indent=2, ensure_ascii=False)

    logger.trace("get_trending_creatives returned %d items", len(results))
    return payload


def handle_generate_creative_script_model(
    args: Dict[str, Any],
) -> str:
    video_id = args["video_id"]
    target_niche = args["target_niche"]
    tone = args.get("tone", DEFAULT_MODELING_TONE)
    logger.debug("Generating creative script model for video '%s' into niche '%s'", video_id, target_niche)

    svc = YouTubeService()
    video = svc.get_video_by_id(video_id)
    if not video:
        logger.warning("Video '%s' not found for script modeling", video_id)
        return json.dumps({"error": f"Video '{video_id}' not found."}, ensure_ascii=False)

    bp = TranscriptService.create_blueprint(video, custom_niche=target_niche)
    payload = {
        "source_title": video.title,
        "source_viral_ratio": f"{video.viral_ratio}x",
        "opening_hook": bp.hook_text,
        "hook_duration_seconds": bp.hook_duration,
        "target_niche": target_niche,
        "tone": tone,
        "suggested_llm_prompt": bp.suggested_prompt,
        "medpy_raw_footage_cut_markers": DEFAULT_MEDPY_CUT_MARKERS,
    }
    result_text = json.dumps(payload, indent=2, ensure_ascii=False)

    logger.trace("Script model created for video %s with %d MedPy cut markers", video_id, len(DEFAULT_MEDPY_CUT_MARKERS))
    return result_text


HANDLERS: Dict[str, Callable[[Dict[str, Any]], str]] = {
    "search_shorts_outliers": handle_search_shorts_outliers,
    "get_video_blueprint": handle_get_video_blueprint,
    "get_trending_creatives": handle_get_trending_creatives,
    "generate_creative_script_model": handle_generate_creative_script_model,
}

TOOLS_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "search_shorts_outliers",
        "description": "Searches vertical short-form outliers (YouTube Shorts) in a specific creator niche. Filters small channels with breakout views and calculates Viral Multipliers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Creator niche or search query (e.g., 'artificial intelligence tools', 'personal finance', 'productivity systems')",
                },
                "max_subscribers": {
                    "type": "integer",
                    "description": f"Maximum channel subscribers (default: {DEFAULT_MAX_SUBSCRIBERS}) to isolate small channels breaking out organically.",
                    "default": DEFAULT_MAX_SUBSCRIBERS,
                },
                "min_views": {
                    "type": "integer",
                    "description": f"Minimum view threshold (default: {DEFAULT_MIN_VIEWS})",
                    "default": DEFAULT_MIN_VIEWS,
                },
                "min_viral_ratio": {
                    "type": "number",
                    "description": f"Minimum Viral Ratio: views / subscribers (default: {DEFAULT_MIN_VIRAL_RATIO}x)",
                    "default": DEFAULT_MIN_VIRAL_RATIO,
                },
                "region_code": {
                    "type": "string",
                    "description": f"Target region ISO code (e.g. '{DEFAULT_REGION}', 'US')",
                    "default": DEFAULT_REGION,
                },
                "max_results": {
                    "type": "integer",
                    "description": f"Maximum number of outlier items (default: {DEFAULT_MCP_MAX_RESULTS})",
                    "default": DEFAULT_MCP_MAX_RESULTS,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_video_blueprint",
        "description": "Dissects a video's opening hook (0-3s), extracts timestamped transcript, calculates Viral Ratio, and returns an actionable creative modeling blueprint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_id": {
                    "type": "string",
                    "description": "YouTube Video ID to dissect",
                },
                "target_niche": {
                    "type": "string",
                    "description": "Target creator niche to adapt the script into",
                },
            },
            "required": ["video_id"],
        },
    },
    {
        "name": "get_trending_creatives",
        "description": "Retrieves real-time trending YouTube Shorts for a target country/category to identify immediate macro trends.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "region_code": {
                    "type": "string",
                    "description": f"ISO country code (default: '{DEFAULT_REGION}')",
                    "default": DEFAULT_REGION,
                },
                "max_results": {
                    "type": "integer",
                    "description": f"Max results to return (default: {DEFAULT_MCP_MAX_RESULTS})",
                    "default": DEFAULT_MCP_MAX_RESULTS,
                },
            },
        },
    },
    {
        "name": "generate_creative_script_model",
        "description": "Generates a scene-by-scene script engineered from an outlier's psychological triggers, adapted for a target niche with MedPy cut markers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_id": {
                    "type": "string",
                    "description": "Source reference video ID",
                },
                "target_niche": {
                    "type": "string",
                    "description": "Target adaptation niche",
                },
                "tone": {
                    "type": "string",
                    "description": f"Tone of voice (e.g. '{DEFAULT_MODELING_TONE}')",
                    "default": DEFAULT_MODELING_TONE,
                },
            },
            "required": ["video_id", "target_niche"],
        },
    },
]


def main():
    logger.info("Underfind Unified MCP Server v%s running via stdio...", SERVICE_VERSION)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _send_error(None, -32700, "Parse error: Invalid JSON")
            continue

        method = req.get("method")
        req_id = req.get("id")
        params = req.get("params", {})

        if method == "initialize":
            _send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "underfind-unified-mcp",
                        "version": SERVICE_VERSION,
                    },
                },
            })

        elif method == "notifications/initialized":
            logger.info("Client successfully initialized Underfind MCP session.")

        elif method == "tools/list":
            _send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS_DEFINITIONS},
            })

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            if tool_name not in HANDLERS:
                _send_error(req_id, -32601, f"Tool '{tool_name}' not found.")
                continue

            try:
                logger.debug("Executing MCP tool '%s' with arguments: %s", tool_name, tool_args)
                handler = HANDLERS[tool_name]
                result_text = handler(tool_args)
                logger.trace("MCP tool '%s' produced %d bytes response", tool_name, len(result_text))

                _send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": result_text}
                        ]
                    },
                })
            except Exception as e:
                logger.error("Error executing tool %s: %s", tool_name, e)
                _send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Execution error: {str(e)}"}
                        ],
                        "isError": True,
                    },
                })

        elif method == "ping":
            _send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})

        else:
            if req_id is not None:
                _send_error(req_id, -32601, f"Method '{method}' not recognized.")


if __name__ == "__main__":
    main()
