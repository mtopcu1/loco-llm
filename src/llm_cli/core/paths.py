"""Load and resolve paths.yaml — the single source of truth for WSL data locations."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

REQUIRED_KEYS = ("data_root", "runtimes", "models", "cache")
_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class Paths:
    data_root: Path
    runtimes: Path
    models: Path
    cache: Path

    def to_env_dict(self) -> dict[str, str]:
        """Render as LLM_* env vars for shell scripts to source."""
        return {
            "LLM_DATA_ROOT": self.data_root.as_posix(),
            "LLM_RUNTIMES": self.runtimes.as_posix(),
            "LLM_MODELS": self.models.as_posix(),
            "LLM_CACHE": self.cache.as_posix(),
        }


def _substitute(value: str, scope: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in scope:
            raise ValueError(f"unresolved variable ${{{key}}}")
        return scope[key]

    return _VAR_RE.sub(repl, value)


def load_paths(path: Path) -> Paths:
    """Load and resolve paths.yaml, expanding ~ and ${var} references.

    Resolution is single-pass with `data_root` available as the only variable.
    This is deliberately simple — paths.yaml is short and has no need for
    arbitrary nesting.
    """
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        raw = {}
    elif not isinstance(loaded, dict):
        raise ValueError("paths.yaml must be a mapping at the top level")
    else:
        raw = loaded

    for key in REQUIRED_KEYS:
        if key not in raw:
            raise ValueError(f"paths.yaml missing required key: {key!r}")
        val = raw[key]
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"paths.yaml key {key!r} must be a non-empty string")

    data_root_raw = str(raw["data_root"])
    data_root = Path(data_root_raw).expanduser()

    scope = {"data_root": str(data_root)}
    resolved: dict[str, Path] = {"data_root": data_root}
    for key in ("runtimes", "models", "cache"):
        substituted = _substitute(str(raw[key]), scope)
        resolved[key] = Path(substituted).expanduser()

    return Paths(**resolved)
