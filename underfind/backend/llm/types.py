from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str


class RateLimited(Exception):
    """The model's quota is exhausted (HTTP 429); the gateway moves to the next model."""


class ProviderUnavailable(RuntimeError):
    """The provider can't serve the request now (no API key, server error, unreachable); the gateway moves to the next role."""


class NoProviderConfigured(ProviderUnavailable):
    """No provider in the role's chain has an API key set; retrying won't help until one is configured."""


class ProviderRefusal(Exception):
    """The model declined or returned nothing usable; the gateway moves to the next model."""


class StructuredOutputError(Exception):
    """No model in the chain returned JSON matching the schema after all attempts."""
