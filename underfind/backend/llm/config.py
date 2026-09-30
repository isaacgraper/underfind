from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict

from underfind.backend.core.constants import ROOT_DIR

DEFAULT_LLM_CONFIG = ROOT_DIR / "config" / "llm.yaml"

ProviderName = Literal["atria", "nvidia", "openrouter", "anthropic", "fake"]


class RoleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    model: str
    # Tried in order when `model` is rate-limited or declines (free-tier quotas are per model).
    fallback_models: List[str] = []
    # Other roles (usually other providers) tried when every model here fails or the provider is unavailable.
    fallback_roles: List[str] = []
    max_tokens: int = 8000
    temperature: Optional[float] = None
    # Provider-specific request fields merged into the body (e.g. reasoning_effort).
    extra: Dict[str, Any] = {}

    @property
    def model_chain(self) -> List[str]:
        return [self.model, *self.fallback_models]


class RolesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: Dict[str, RoleConfig]

    def get(self, role: str) -> RoleConfig:
        try:
            return self.roles[role]
        except KeyError:
            raise KeyError(f"unknown LLM role: {role!r}") from None


def load_roles(path: Optional[Path] = None) -> RolesFile:
    """Reads config/llm.yaml (or LLM_CONFIG). UNDERFIND_<ROLE>_MODEL env vars override a role's primary model."""
    config_path = path or Path(os.environ.get("LLM_CONFIG") or DEFAULT_LLM_CONFIG)
    roles = RolesFile.model_validate(yaml.safe_load(config_path.read_text(encoding="utf-8")))

    for name, cfg in list(roles.roles.items()):
        override = os.environ.get(f"UNDERFIND_{name.upper()}_MODEL", "").strip()

        if override:
            roles.roles[name] = cfg.model_copy(update={"model": override, "fallback_models": []})

    return roles
