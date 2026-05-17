"""User-level settings stored at ~/.config/llm/config.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    data_root: Path
    repo_root: Path
    runtimes_dir: Path
    models_dir: Path
    cache_dir: Path


KEY_REGISTRY: dict[str, dict[str, Any]] = {
    "data_root": {
        "default": "~/llm",
        "required": True,
        "prompt": "Where should LocalLLM store runtimes, models, and cache?",
        "kind": "path",
    },
    "repo_root": {
        "default": None,
        "required": True,
        "prompt": "Path to the LocalLLM repo clone",
        "kind": "path",
    },
    "runtimes_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "runtimes",
        "prompt": "Override runtimes directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
    "models_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "models",
        "prompt": "Override models directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
    "cache_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "cache",
        "prompt": "Override cache directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
}


def default_settings() -> dict[str, str]:
    """The minimum stored dict; repo_root is filled in by `llm setup`."""
    return {"data_root": KEY_REGISTRY["data_root"]["default"]}
