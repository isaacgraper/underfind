from __future__ import annotations

import json
import re
import threading
from typing import Callable, Dict, List, Mapping, Optional, Tuple, TypeVar

from pydantic import BaseModel, ValidationError

from underfind.backend.core.logger import logger
from underfind.backend.llm.config import RoleConfig, RolesFile, load_roles
from underfind.backend.llm.providers import PROVIDER_CLASSES, MissingKey, Provider
from underfind.backend.llm.types import (
    Completion,
    NoProviderConfigured,
    ProviderRefusal,
    ProviderUnavailable,
    RateLimited,
    StructuredOutputError,
)

T = TypeVar("T", bound=BaseModel)

MAX_SCHEMA_ATTEMPTS = 3
_FENCE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)


def strip_fences(text: str) -> str:
    match = _FENCE.match(text)
    return match.group(1).strip() if match else text.strip()


def extract_json(text: str) -> str:
    """Model output minus code fences and any prose before the first { or after the last }."""
    clean = strip_fences(text)
    start, end = clean.find("{"), clean.rfind("}")
    return clean[start:end + 1] if start != -1 and end > start else clean


class LazyProviders(Mapping[str, Provider]):
    """Builds a provider on first use, so a missing key only matters when a role reaches that provider."""

    def __init__(self, factories: Dict[str, Callable[[], Provider]]):
        self._factories = factories
        self._built: Dict[str, Provider] = {}
        self._lock = threading.Lock()

    def __getitem__(self, name: str) -> Provider:
        with self._lock:
            if name not in self._built:
                self._built[name] = self._factories[name]()

            return self._built[name]

    def __iter__(self):
        return iter(self._factories)

    def __len__(self) -> int:
        return len(self._factories)


class Gateway:
    """
    Single entry point for LLM calls. A role names a provider and a model chain; on a rate limit or refusal
    the next model is tried, and when the provider has no key, is down, or every model failed, the role's
    fallback roles (other providers) are tried in order, one level deep.
    """

    def __init__(
        self,
        roles: RolesFile,
        providers: Mapping[str, Provider],
    ):
        self.roles = roles
        self.providers = providers

    def complete(self, role: str, prompt: str, *, system: Optional[str] = None) -> Completion:
        cfg = self.roles.get(role)
        chain: List[Tuple[str, RoleConfig]] = [(role, cfg)] + [(r, self.roles.get(r)) for r in cfg.fallback_roles]
        reasons: List[str] = []
        missing_keys = 0

        for role_name, role_cfg in chain:
            try:
                provider = self.providers[role_cfg.provider]
            except ProviderUnavailable as err:
                missing_keys += isinstance(err, MissingKey)
                reasons.append(f"{role_name}: {err}")
                continue

            for model in role_cfg.model_chain:
                try:
                    completion = provider.complete(role_cfg.model_copy(update={"model": model}), system, prompt)
                except RateLimited:
                    reasons.append(f"{role_cfg.provider}/{model}: rate-limited")
                    continue
                except ProviderRefusal as err:
                    reasons.append(f"{role_cfg.provider}/{model}: {err}")
                    continue
                except ProviderUnavailable as err:
                    reasons.append(f"{role_cfg.provider}/{model}: {err}")
                    break

                logger.debug("LLM role %s served by %s/%s (%d in, %d out)", role, completion.provider, completion.model, completion.input_tokens, completion.output_tokens)
                return completion

        logger.warning("LLM role %s: no model could serve the request: %s", role, reasons)

        if missing_keys == len(chain):
            raise NoProviderConfigured(f"role {role!r}: no API key set for any provider in its chain: {reasons}")

        if reasons and all("rate-limited" in r for r in reasons):
            raise RateLimited(f"role {role!r}: every model is rate-limited: {reasons}")

        raise ProviderUnavailable(f"role {role!r}: no usable model: {reasons}")

    def generate_structured(
        self,
        role: str,
        prompt: str,
        schema: type[T],
        *,
        system: Optional[str] = None,
    ) -> Tuple[T, Completion]:
        """JSON validated against a Pydantic schema; invalid output is sent back with the error, up to 3 attempts."""
        schema_json = json.dumps(schema.model_json_schema(), sort_keys=True)
        base = f"{prompt}\n\nReturn only JSON matching this JSON Schema, with no prose and no code fences:\n{schema_json}"
        request = base
        last_error = ""

        for _ in range(MAX_SCHEMA_ATTEMPTS):
            completion = self.complete(role, request, system=system)
            raw = extract_json(completion.text)

            try:
                return schema.model_validate_json(raw), completion
            except ValidationError as err:
                last_error = str(err)
                request = f"{base}\n\nYour previous output was invalid.\nPrevious output:\n{raw[:4000]}\n\nValidation error:\n{last_error[:2000]}"

        raise StructuredOutputError(f"role {role!r} failed schema {schema.__name__} after {MAX_SCHEMA_ATTEMPTS} attempts: {last_error[:500]}")


_default_gateway: Optional[Gateway] = None
_default_lock = threading.Lock()


def get_gateway() -> Gateway:
    global _default_gateway

    with _default_lock:
        if _default_gateway is None:
            _default_gateway = Gateway(load_roles(), LazyProviders(PROVIDER_CLASSES))

        return _default_gateway
