from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
import pytest

from underfind.backend.core.errors import PermanentStageError
from underfind.backend.llm.config import RoleConfig, RolesFile, load_roles
from underfind.backend.llm.gateway import Gateway, LazyProviders, extract_json
from underfind.backend.llm.providers import (
    AtriaProvider,
    MissingKey,
    NvidiaProvider,
    OpenRouterProvider,
    RateLimiter,
)
from underfind.backend.llm.types import (
    Completion,
    NoProviderConfigured,
    ProviderRefusal,
    ProviderUnavailable,
    RateLimited,
    StructuredOutputError,
)
from underfind.backend.pipeline.translate import LLMTranslator, SegmentInput, TranslationDraft, TranslationInput


def _ok(text: str, model: str = "m") -> Dict[str, Any]:
    return {
        "model": model,
        "choices": [{"message": {"content": text, "reasoning_content": "THINKING"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _client(handler) -> httpx.Client:
    return httpx.Client(base_url="https://example.test/v1", transport=httpx.MockTransport(handler))


def _cfg(model: str = "moonshotai/kimi-k3", **kwargs) -> RoleConfig:
    return RoleConfig(provider="nvidia", model=model, **kwargs)


# ---------------------------------------------------------------- providers


def test_openai_compat_request_shape_and_answer_only():
    seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_ok("Olá", model="moonshotai/kimi-k3"))

    provider = NvidiaProvider(api_key="nv-key", client=_client(handler), limiter=None)
    provider.limiter = None
    completion = provider.complete(_cfg(temperature=0.4, extra={"reasoning_effort": "low"}), "sys", "hi")

    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/v1/chat/completions"
    assert seen[0].headers["Authorization"] == "Bearer nv-key"
    assert body["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    assert body["temperature"] == 0.4 and body["reasoning_effort"] == "low" and body["max_tokens"] == 8000
    assert completion.text == "Olá" and completion.provider == "nvidia" and completion.input_tokens == 10


@pytest.mark.parametrize("status, body, expected", [
    (429, {"error": "slow down"}, RateLimited),
    (503, {"error": "overloaded"}, ProviderUnavailable),
    (404, {"error": "no such model"}, ProviderRefusal),
    (200, {"error": {"code": 429, "message": "daily limit"}}, RateLimited),
    (200, {"choices": [{"message": {"content": "  "}}]}, ProviderRefusal),
])
def test_openai_compat_error_mapping(status, body, expected):
    provider = AtriaProvider(api_key="k", client=_client(lambda r: httpx.Response(status, json=body)))

    with pytest.raises(expected):
        provider.complete(_cfg("Atria-Dawn-Preview"), None, "hi")


def test_openai_compat_network_error_is_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderUnavailable):
        OpenRouterProvider(api_key="k", client=_client(handler)).complete(_cfg(), None, "hi")


def test_missing_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(MissingKey):
        OpenRouterProvider()


def test_openrouter_headers():
    seen: List[httpx.Request] = []
    provider = OpenRouterProvider(api_key="k", client=_client(lambda r: seen.append(r) or httpx.Response(200, json=_ok("x"))))
    provider.complete(_cfg(), None, "hi")

    assert seen[0].headers["X-Title"] == "underfind"


def test_rate_limiter_waits_when_window_is_full():
    now = [0.0]
    sleeps: List[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(2, clock=lambda: now[0], sleep=sleep)
    limiter.acquire()
    now[0] = 10.0
    limiter.acquire()
    limiter.acquire()

    assert sleeps == [50.0]


# ------------------------------------------------------------------ gateway


class FakeProvider:
    def __init__(self, name: str, script: Dict[str, List[Any]]):
        self.name = name
        self.script = script
        self.calls: List[str] = []

    def complete(self, cfg: RoleConfig, system: Optional[str], prompt: str) -> Completion:
        self.calls.append(cfg.model)
        outcome = self.script[cfg.model].pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return Completion(outcome, 1, 1, cfg.model, self.name)


def _roles() -> RolesFile:
    return RolesFile(roles={
        "translator": RoleConfig(provider="nvidia", model="kimi", fallback_models=["nemotron"], fallback_roles=["backup", "last"]),
        "backup": RoleConfig(provider="atria", model="dawn"),
        "last": RoleConfig(provider="openrouter", model="venice:free"),
    })


class _Providers(dict):
    """Mapping that raises like LazyProviders when a provider can't be built."""

    def __getitem__(self, name):
        value = super().__getitem__(name)

        if isinstance(value, Exception):
            raise value

        return value


def test_gateway_falls_through_models_then_roles():
    nvidia = FakeProvider("nvidia", {"kimi": [RateLimited("quota")], "nemotron": [ProviderRefusal("empty")]})
    atria = FakeProvider("atria", {"dawn": [ProviderUnavailable("HTTP 502")]})
    openrouter = FakeProvider("openrouter", {"venice:free": ["ok"]})
    gateway = Gateway(_roles(), _Providers(nvidia=nvidia, atria=atria, openrouter=openrouter))

    completion = gateway.complete("translator", "hi")

    assert completion.provider == "openrouter"
    assert nvidia.calls == ["kimi", "nemotron"] and atria.calls == ["dawn"]


def test_gateway_skips_providers_without_keys():
    openrouter = FakeProvider("openrouter", {"venice:free": ["ok"]})
    gateway = Gateway(_roles(), _Providers(nvidia=MissingKey("NVIDIA_API_KEY is not set"), atria=MissingKey("x"), openrouter=openrouter))

    assert gateway.complete("translator", "hi").provider == "openrouter"


def test_gateway_error_kinds():
    no_keys = Gateway(_roles(), _Providers(nvidia=MissingKey("a"), atria=MissingKey("b"), openrouter=MissingKey("c")))
    with pytest.raises(NoProviderConfigured):
        no_keys.complete("translator", "hi")

    limited = Gateway(_roles(), _Providers(
        nvidia=FakeProvider("nvidia", {"kimi": [RateLimited("q")], "nemotron": [RateLimited("q")]}),
        atria=FakeProvider("atria", {"dawn": [RateLimited("q")]}),
        openrouter=FakeProvider("openrouter", {"venice:free": [RateLimited("q")]}),
    ))
    with pytest.raises(RateLimited):
        limited.complete("translator", "hi")


def test_generate_structured_retries_with_validation_error():
    nvidia = FakeProvider("nvidia", {"kimi": [
        "Sure! Here is the JSON:\n```json\n{\"caption\": 5}\n```",
        '```json\n{"caption": "ok", "hashtags": ["#gta6"]}\n```',
    ]})
    gateway = Gateway(_roles(), _Providers(nvidia=nvidia))

    draft, completion = gateway.generate_structured("translator", "translate", TranslationDraft)

    assert draft.caption == "ok" and draft.hashtags == ["#gta6"]
    assert len(nvidia.calls) == 2


def test_generate_structured_gives_up():
    nvidia = FakeProvider("nvidia", {"kimi": ["nope", "still nope", "never"]})
    gateway = Gateway(_roles(), _Providers(nvidia=nvidia))

    with pytest.raises(StructuredOutputError):
        gateway.generate_structured("translator", "translate", TranslationDraft)


def test_extract_json():
    assert extract_json('noise {"a": 1} trailing') == '{"a": 1}'
    assert extract_json('```\n{"a": 1}\n```') == '{"a": 1}'


def test_lazy_providers_build_once():
    built: List[str] = []
    providers = LazyProviders({"atria": lambda: built.append("atria") or "provider"})

    assert providers["atria"] == "provider" and providers["atria"] == "provider"
    assert built == ["atria"]


def test_default_config_is_free_first(monkeypatch):
    monkeypatch.setenv("UNDERFIND_TRANSLATOR_MODEL", "nvidia/other-model")
    roles = load_roles()
    translator = roles.get("translator")

    assert translator.provider == "nvidia" and translator.model_chain == ["nvidia/other-model"]
    chain = [roles.get(r).provider for r in translator.fallback_roles]
    assert chain == ["atria", "openrouter"]
    assert "anthropic" not in [translator.provider, *chain]


# --------------------------------------------------------------- translator


def _req() -> TranslationInput:
    return TranslationInput(
        target_language="pt-BR",
        source_language="en",
        mode="subtitles",
        segments=[SegmentInput(index=0, start=0, end=2, text="Hello Vice City", max_chars=34)],
        glossary=["Vice City"],
    )


def test_llm_translator_uses_translator_role_and_records_model():
    answer = '{"segments": [{"index": 0, "text": "Fala, Vice City"}], "caption": "c", "hashtags": ["#gta6"], "onscreen_text": []}'
    nvidia = FakeProvider("nvidia", {"kimi": [answer]})
    prompts: List[str] = []
    original = nvidia.complete
    nvidia.complete = lambda cfg, system, prompt: prompts.append(prompt) or original(cfg, system, prompt)
    translator = LLMTranslator(gateway=Gateway(_roles(), _Providers(nvidia=nvidia)))

    draft = translator.translate(_req())

    assert draft.segments[0].text == "Fala, Vice City"
    assert translator.model == "nvidia/kimi"
    assert '"max_chars": 34' in prompts[0] and "Vice City" in prompts[0]


def test_llm_translator_without_keys_fails_permanently():
    gateway = Gateway(_roles(), _Providers(nvidia=MissingKey("a"), atria=MissingKey("b"), openrouter=MissingKey("c")))

    with pytest.raises(PermanentStageError, match="no API key"):
        LLMTranslator(gateway=gateway).translate(_req())


def test_llm_translator_schema_failure_is_retryable():
    gateway = Gateway(_roles(), _Providers(nvidia=FakeProvider("nvidia", {"kimi": ["x", "y", "z"]})))

    with pytest.raises(RuntimeError):
        LLMTranslator(gateway=gateway).translate(_req())
