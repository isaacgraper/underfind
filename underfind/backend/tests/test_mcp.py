from __future__ import annotations

import json
from underfind.backend.mcp.server import HANDLERS, TOOLS_DEFINITIONS


def test_mcp_handlers_dict_is_constant():
    assert isinstance(HANDLERS, dict)
    expected_tools = {
        "search_shorts_outliers",
        "get_video_blueprint",
        "get_trending_creatives",
        "generate_creative_script_model",
    }
    assert set(HANDLERS.keys()) == expected_tools


def test_mcp_tools_definitions_match_handlers():
    assert isinstance(TOOLS_DEFINITIONS, list)
    defined_names = {t["name"] for t in TOOLS_DEFINITIONS}
    assert defined_names == set(HANDLERS.keys())


def test_mcp_handler_callables():
    for name, handler in HANDLERS.items():
        assert callable(handler)
