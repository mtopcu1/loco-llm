"""Auto-fill serve params bound to the config's selected model."""
from __future__ import annotations

from llm_cli.core.params import ParamSpec

MODEL_PATH_TOKEN = "${model_path}"


def bound_keys_to_skip(specs: list[ParamSpec], *, model_id: str | None) -> set[str]:
    if not model_id:
        return set()
    return {s.key for s in specs if s.bind == "model_path"}


def apply_model_bindings(
    specs: list[ParamSpec],
    raw: dict[str, str],
    *,
    model_id: str | None,
) -> dict[str, str]:
    out = dict(raw)
    if not model_id:
        return out
    for spec in specs:
        if spec.bind != "model_path":
            continue
        if spec.key not in out:
            out[spec.key] = MODEL_PATH_TOKEN
    return out
