"""Versioned YAML prompt loader (decision #15).

Each prompt file:

    name: personality_system_v1
    version: 1
    description: System prompt for LLM personality embedder
    content: |
      You are an expert astrologer and personality analyst...

Loaded prompts are cached and accessed by canonical path, e.g.:

    personality/system     → prompts/personality/system.yaml
    spotlight/narrative    → prompts/spotlight/narrative.yaml
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from string import Template

import yaml

from realm.core.config import PROJECT_ROOT
from realm.core.exceptions import DataError

PROMPTS_DIR = PROJECT_ROOT / "prompts"


@dataclass(frozen=True, slots=True)
class Prompt:
    name: str
    version: int
    description: str
    content: str
    path: str

    def render(self, **values) -> str:
        """Substitute `$var` placeholders using string.Template."""
        return Template(self.content).safe_substitute(**values)


@lru_cache(maxsize=128)
def load_prompt(key: str) -> Prompt:
    """Load a prompt by 'category/name' (without .yaml)."""
    path = PROMPTS_DIR / f"{key}.yaml"
    if not path.exists():
        raise DataError(f"prompt file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise DataError(f"invalid YAML in prompt {path}: {e}") from e

    try:
        return Prompt(
            name=str(data["name"]),
            version=int(data.get("version", 1)),
            description=str(data.get("description", "")),
            content=str(data["content"]),
            path=str(path),
        )
    except KeyError as e:
        raise DataError(f"prompt {path} missing required key: {e}") from e


def clear_cache() -> None:
    load_prompt.cache_clear()
