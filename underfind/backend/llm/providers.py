from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Protocol

import httpx

from underfind.backend.llm.config import RoleConfig
from underfind.backend.llm.types import Completion, ProviderRefusal, ProviderUnavailable, RateLimited


class Provider(Protocol):
    name: str

    def complete(self, cfg: RoleConfig, system: Optional[str], prompt: str) -> Completion:
        ...


class MissingKey(ProviderUnavailable):
    """The provider's API key env var isn't set; the gateway falls back to another role."""


class APIError(RuntimeError):
    """A client-side error (bad request, auth) that retrying elsewhere with the same payload won't fix."""


class RateLimiter:
    """Sliding window: at most `rpm` requests per 60 s; waits instead of failing."""

    def __init__(
        self,
        rpm: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.rpm = rpm
        self.clock = clock
        self.sleep = sleep
        self.sent: Deque[float] = deque()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        with self.lock:
            now = self.clock()

            while self.sent and now - self.sent[0] >= 60.0:
                self.sent.popleft()

            if len(self.sent) >= self.rpm:
                self.sleep(60.0 - (now - self.sent[0]))
                now = self.clock()
                self.sent.popleft()

            self.sent.append(now)


class OpenAICompatProvider:
    """Chat-completions over HTTP for OpenAI-compatible services (Atria, NVIDIA, OpenRouter)."""

    name = "openai-compatible"
    base_url = ""
    key_env = ""
    key_help = ""
    rpm: Optional[int] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        client: Optional[httpx.Client] = None,
        timeout: float = 300.0,
        limiter: Optional[RateLimiter] = None,
    ):
        key = api_key or os.environ.get(self.key_env, "")

        if not key:
            raise MissingKey(f"{self.key_env} is not set ({self.key_help}; see .env.example)")

        self.client = client or httpx.Client(base_url=self.base_url, timeout=timeout)
        self.client.headers.update({"Authorization": f"Bearer {key}", **self.extra_headers()})
        self.limiter = limiter or (RateLimiter(self.rpm) if self.rpm else None)

    def extra_headers(self) -> Dict[str, str]:
        return {}

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.limiter:
            self.limiter.acquire()

        try:
            resp = self.client.post("/chat/completions", json=payload)
        except httpx.TransportError as err:
            raise ProviderUnavailable(f"{self.name} unreachable: {err}") from err

        label = f"{self.name} {payload['model']}"

        if resp.status_code == 429:
            raise RateLimited(f"{label}: {resp.text[:300]}")

        if resp.status_code >= 500:
            raise ProviderUnavailable(f"{label}: HTTP {resp.status_code}: {resp.text[:300]}")

        if resp.status_code == 404:
            raise ProviderRefusal(f"{label}: model not found (HTTP 404)")

        if resp.status_code >= 400:
            raise APIError(f"{label}: HTTP {resp.status_code}: {resp.text[:300]}")

        data: Dict[str, Any] = resp.json()

        if "error" in data:
            err = data["error"]

            if isinstance(err, dict) and err.get("code") == 429:
                raise RateLimited(f"{label}: {err.get('message', err)}")

            raise ProviderUnavailable(f"{label}: {err}")

        return data

    def complete(self, cfg: RoleConfig, system: Optional[str], prompt: str) -> Completion:
        messages: List[Dict[str, str]] = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})
        payload: Dict[str, Any] = {**cfg.extra, "model": cfg.model, "messages": messages, "max_tokens": cfg.max_tokens}

        if cfg.temperature is not None:
            payload["temperature"] = cfg.temperature

        data = self._post(payload)
        choices = data.get("choices") or []

        if not choices:
            raise ProviderRefusal(f"{cfg.model} returned no choices")

        # Only the answer: reasoning fields (reasoning_content etc.) are ignored.
        text = (choices[0].get("message") or {}).get("content") or ""

        if not text.strip():
            raise ProviderRefusal(f"{cfg.model} returned empty text")

        usage = data.get("usage") or {}
        return Completion(
            text=text,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            model=str(data.get("model") or cfg.model),
            provider=self.name,
        )


class AtriaProvider(OpenAICompatProvider):
    """Atria (Shanghai AI Lab, Atria-Dawn-Preview). Free tier: 100M tokens."""

    name = "atria"
    base_url = "https://api.atria-asi.ai/v1"
    key_env = "ATRIA_API_KEY"
    key_help = "key from the API Console at api.atria-asi.ai"


class NvidiaProvider(OpenAICompatProvider):
    """NVIDIA API catalog. Free: 40 requests/min, throttled client-side to 38."""

    name = "nvidia"
    base_url = "https://integrate.api.nvidia.com/v1"
    key_env = "NVIDIA_API_KEY"
    key_help = "free key at build.nvidia.com"
    rpm = 38


class OpenRouterProvider(OpenAICompatProvider):
    """OpenRouter free models (~50 requests/day without credits)."""

    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"
    key_env = "OPENROUTER_API_KEY"
    key_help = "free key at openrouter.ai/keys"

    def extra_headers(self) -> Dict[str, str]:
        return {
            "HTTP-Referer": os.environ.get("OPENROUTER_REFERER") or "https://github.com/isaacgraper/underfind",
            "X-Title": os.environ.get("OPENROUTER_TITLE") or "underfind",
        }


class AnthropicProvider:
    """Claude (paid). Only used by roles that name it; never part of the default chain."""

    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None):
        try:
            import anthropic
        except ImportError as err:
            raise ProviderUnavailable("anthropic package not installed (poetry install -E claude)") from err

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if not key:
            raise MissingKey("ANTHROPIC_API_KEY is not set")

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=key)

    def complete(self, cfg: RoleConfig, system: Optional[str], prompt: str) -> Completion:
        kwargs: Dict[str, Any] = {
            "model": cfg.model,
            "max_tokens": cfg.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            **cfg.extra,
        }

        if system:
            kwargs["system"] = system

        try:
            with self.client.messages.stream(**kwargs) as stream:
                message = stream.get_final_message()
        except self._anthropic.RateLimitError as err:
            raise RateLimited(f"{cfg.model}: {err.message}") from err
        except (self._anthropic.InternalServerError, self._anthropic.APIConnectionError) as err:
            raise ProviderUnavailable(f"{cfg.model}: {err}") from err

        if message.stop_reason == "refusal":
            raise ProviderRefusal(f"{cfg.model} refused")

        text = "".join(block.text for block in message.content if block.type == "text")
        return Completion(text, message.usage.input_tokens, message.usage.output_tokens, message.model, self.name)


PROVIDER_CLASSES: Dict[str, Callable[[], Provider]] = {
    "atria": AtriaProvider,
    "nvidia": NvidiaProvider,
    "openrouter": OpenRouterProvider,
    "anthropic": AnthropicProvider,
}
