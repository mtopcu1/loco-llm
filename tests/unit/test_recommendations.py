"""Tests for VRAM-aware recommendations (llamacpp only in v1)."""
from __future__ import annotations

from llm_cli.core.model_registry import Artifact, HFSource, Metadata, RegistryEntry
from llm_cli.core.specs import CpuInfo, GpuInfo, SystemSpecs


def _mk_model(size_bytes: int) -> RegistryEntry:
    return RegistryEntry(
        id="m",
        format="gguf",
        source=HFSource(repo="r"),
        artifact=Artifact(
            primary="m.gguf",
            files=("m.gguf",),
            total_size_bytes=size_bytes,
        ),
        metadata=Metadata(),
        installed_at="",
    )


def _mk_specs(vram_gb: int) -> SystemSpecs:
    return SystemSpecs(
        cpu=CpuInfo(model="X", logical_cores=1),
        ram_gb=16,
        gpus=[GpuInfo(index=0, name="Test GPU", vram_gb=vram_gb, driver="0")],
    )


def test_recommend_returns_none_for_non_llamacpp():
    from llm_cli.core.recommendations import recommend

    out = recommend("vllm", "ctx", model=_mk_model(10 * 1024**3), specs=_mk_specs(24))
    assert out is None


def test_recommend_returns_none_when_no_gpu():
    from llm_cli.core.recommendations import recommend

    specs = SystemSpecs(cpu=CpuInfo(model="X", logical_cores=1), ram_gb=16, gpus=[])
    out = recommend("llamacpp", "ctx", model=_mk_model(10 * 1024**3), specs=specs)
    assert out is None


def test_recommend_returns_none_when_model_size_unknown():
    from llm_cli.core.recommendations import recommend

    out = recommend("llamacpp", "ctx", model=_mk_model(0), specs=_mk_specs(24))
    assert out is None


def test_recommend_ctx_when_model_fits_in_vram():
    from llm_cli.core.recommendations import recommend

    out = recommend("llamacpp", "ctx", model=_mk_model(8 * 1024**3), specs=_mk_specs(24))
    assert out is not None
    assert out.value in {"4096", "8192"}
    assert "VRAM" in out.reason


def test_recommend_ctx_conservative_when_model_exceeds_vram():
    from llm_cli.core.recommendations import recommend

    out = recommend(
        "llamacpp", "ctx", model=_mk_model(35 * 1024**3), specs=_mk_specs(24)
    )
    assert out is not None
    assert out.value == "4096"
    lo = out.reason.lower()
    assert "exceeds" in lo or "conservative" in lo


def test_recommend_n_gpu_layers_all_when_fits():
    from llm_cli.core.recommendations import recommend

    out = recommend(
        "llamacpp",
        "n_gpu_layers",
        model=_mk_model(8 * 1024**3),
        specs=_mk_specs(24),
    )
    assert out is not None
    assert out.value == "-1"
    assert "fit" in out.reason.lower()


def test_recommend_n_gpu_layers_partial_when_overflows():
    from llm_cli.core.recommendations import recommend

    out = recommend(
        "llamacpp",
        "n_gpu_layers",
        model=_mk_model(35 * 1024**3),
        specs=_mk_specs(24),
    )
    assert out is not None
    n = int(out.value)
    assert 30 <= n <= 50


def test_recommend_returns_none_for_unknown_param_key():
    from llm_cli.core.recommendations import recommend

    out = recommend(
        "llamacpp",
        "totally_made_up",
        model=_mk_model(8 * 1024**3),
        specs=_mk_specs(24),
    )
    assert out is None
