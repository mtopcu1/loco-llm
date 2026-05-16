from llm_cli.core.specs import (
    CpuInfo,
    GpuInfo,
    OsInfo,
    SystemSpecs,
    WslInfo,
    render_specs_block,
)


def _example_specs() -> SystemSpecs:
    return SystemSpecs(
        cpu=CpuInfo(model="AMD Ryzen 9 7950X 16-Core Processor", logical_cores=32),
        ram_gb=64,
        gpus=[GpuInfo(index=0, name="NVIDIA GeForce RTX 4090", vram_gb=24, driver="560.94")],
        cuda_runtime="12.6",
        os=OsInfo(description="Microsoft Windows [Version 10.0.22631.4111]"),
        wsl=WslInfo(distro="Ubuntu 22.04.4 LTS", kernel="5.15.153.1-microsoft-standard-WSL2"),
        systemd_enabled=True,
        repo_root="/mnt/c/Private/Projects/LocalLLM",
        data_root="/home/melih/llm",
    )


def test_render_specs_block_contains_all_sections() -> None:
    md = render_specs_block(_example_specs(), generated_at="2026-05-15T18:30:00Z")
    assert "_Generated: 2026-05-15T18:30:00Z_" in md
    assert "## Host" in md
    assert "AMD Ryzen 9 7950X" in md
    assert "64 GB" in md
    assert "## GPU" in md
    assert "RTX 4090" in md
    assert "560.94" in md
    assert "CUDA runtime: 12.6" in md
    assert "## WSL" in md
    assert "Ubuntu 22.04" in md
    assert "microsoft-standard-WSL2" in md
    assert "Systemd:** enabled" in md
    assert "## Storage layout" in md
    assert "/mnt/c/Private/Projects/LocalLLM" in md
    assert "/home/melih/llm" in md


def test_render_specs_block_no_gpu_falls_back_gracefully() -> None:
    specs = SystemSpecs(
        cpu=CpuInfo(model="cpu", logical_cores=1),
        ram_gb=8,
    )
    md = render_specs_block(specs, generated_at="2026-05-15T18:30:00Z")
    assert "## GPU" in md
    assert "_No GPU detected._" in md


def test_render_specs_block_systemd_disabled_label() -> None:
    specs = SystemSpecs(
        cpu=CpuInfo(model="cpu", logical_cores=1),
        ram_gb=8,
        wsl=WslInfo(distro="Ubuntu", kernel="x"),
        systemd_enabled=False,
    )
    md = render_specs_block(specs, generated_at="2026-05-15T18:30:00Z")
    assert "Systemd:** disabled" in md
