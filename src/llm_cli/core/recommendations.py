"""VRAM-aware heuristics for `llm advisor` (llamacpp v1)."""
from __future__ import annotations

from dataclasses import dataclass

from llm_cli.core.model_registry import RegistryEntry
from llm_cli.core.specs import SystemSpecs


@dataclass(frozen=True)
class Recommendation:
    value: str
    reason: str


@dataclass(frozen=True)
class AdvisorHint:
    param_key: str
    suggested_value: str
    reason: str
    confidence: float | None = None

    def as_dict(self) -> dict[str, str | float | None]:
        return {
            "param_key": self.param_key,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "confidence": self.confidence,
        }


_HEADROOM_BYTES = 1 << 30
_KV_BYTES_PER_TOKEN = 2 << 20
_LAYERS_ASSUMED = 60


def _max_gpu_vram_bytes(specs: SystemSpecs) -> int:
    if not specs.gpus:
        return 0
    return max(g.vram_gb for g in specs.gpus) * (1 << 30)


def _snap_pow2(n: int, *, minimum: int) -> int:
    if n < minimum:
        return minimum
    p = minimum
    while p * 2 <= n:
        p *= 2
    return p


def _gb_text(bytes_: int) -> str:
    return f"{bytes_ / (1 << 30):.1f} GB"


def recommend(
    runtime_id: str,
    param_key: str,
    *,
    model: RegistryEntry | None,
    specs: SystemSpecs | None,
) -> Recommendation | None:
    """Best-effort suggestion or None when prerequisites are missing."""
    if runtime_id != "llamacpp":
        return None
    if model is None or specs is None:
        return None
    weights = model.artifact.total_size_bytes
    if weights <= 0:
        return None
    total_vram = _max_gpu_vram_bytes(specs)
    if total_vram <= 0:
        return None
    free_vram = max(0, total_vram - _HEADROOM_BYTES)

    if param_key == "ctx":
        available_for_kv = max(0, free_vram - weights)
        if available_for_kv <= 0:
            return Recommendation(
                value="4096",
                reason=(
                    f"estimate: weights {_gb_text(weights)} exceed VRAM headroom "
                    f"{_gb_text(free_vram)} after reserving {_gb_text(_HEADROOM_BYTES)}; "
                    "conservative ctx"
                ),
            )
        approx_tokens = available_for_kv // _KV_BYTES_PER_TOKEN
        suggested = _snap_pow2(approx_tokens, minimum=2048)
        return Recommendation(
            value=str(suggested),
            reason=(
                f"estimate: {_gb_text(total_vram)} VRAM, {_gb_text(weights)} weights; "
                f"~{approx_tokens} tokens budget for KV (rough)"
            ),
        )

    if param_key == "n_gpu_layers":
        if weights <= free_vram:
            return Recommendation(
                value="-1",
                reason="estimate: weights appear to fit remaining VRAM headroom",
            )
        suggested = max(1, int((free_vram / weights) * _LAYERS_ASSUMED))
        return Recommendation(
            value=str(suggested),
            reason=(
                f"estimate: linear scaling vs {_LAYERS_ASSUMED} layers & relative VRAM "
                f"({_gb_text(free_vram)} / {_gb_text(weights)})"
            ),
        )

    return None


def compute(runtime_id: str, *, model_id: str | None = None) -> list[AdvisorHint]:
    """REST-friendly advisor hints for (runtime_id, model_id), mirroring ``llm advisor``."""
    from llm_cli.core import registry
    from llm_cli.core.model_registry import get_entry
    from llm_cli.core.scaffold import scaffold_root
    from llm_cli.core.settings import load_settings, resolve
    from llm_cli.core.specs import detect_all

    if not model_id:
        return []

    rt_manifest = registry.get_runtime_manifest_merged(runtime_id)
    if rt_manifest is None:
        return []

    settings = resolve(load_settings())
    model = get_entry(settings.models_dir, model_id)
    if model is None:
        return []

    specs = detect_all(
        repo_root=scaffold_root().as_posix(),
        data_root=settings.data_root.as_posix(),
    )
    out: list[AdvisorHint] = []
    for spec in rt_manifest.serve_schema:
        rec = recommend(runtime_id, spec.key, model=model, specs=specs)
        if rec is None:
            continue
        out.append(
            AdvisorHint(
                param_key=spec.key,
                suggested_value=rec.value,
                reason=rec.reason,
            )
        )
    return out
