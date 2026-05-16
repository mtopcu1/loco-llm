from __future__ import annotations

import pytest

from llm_cli.core.shell import CommandResult
from llm_cli.core.specs import (
    CpuInfo,
    GpuInfo,
    OsInfo,
    WslInfo,
    detect_cpu,
    detect_gpus,
    detect_os,
    detect_ram_gb,
    detect_wsl,
    parse_meminfo_total_kb,
    parse_nvidia_smi_csv,
    parse_proc_cpuinfo,
)


SAMPLE_CPUINFO = """\
processor\t: 0
vendor_id\t: AuthenticAMD
model name\t: AMD Ryzen 9 7950X 16-Core Processor
cpu MHz\t\t: 4500.000
cache size\t: 1024 KB

processor\t: 1
vendor_id\t: AuthenticAMD
model name\t: AMD Ryzen 9 7950X 16-Core Processor
cpu MHz\t\t: 4500.000
"""


SAMPLE_NVIDIA_SMI_CSV = """\
0, NVIDIA GeForce RTX 4090, 24564 MiB, 560.94
1, NVIDIA GeForce RTX 4090, 24564 MiB, 560.94
"""


def test_parse_proc_cpuinfo_extracts_model_and_count() -> None:
    info = parse_proc_cpuinfo(SAMPLE_CPUINFO)
    assert info.model == "AMD Ryzen 9 7950X 16-Core Processor"
    assert info.logical_cores == 2  # the sample has 2 entries


def test_parse_proc_cpuinfo_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_proc_cpuinfo("")


def test_parse_meminfo_total_kb() -> None:
    sample = (
        "MemTotal:       65816184 kB\n"
        "MemFree:         1234567 kB\n"
        "MemAvailable:   45678901 kB\n"
    )
    assert parse_meminfo_total_kb(sample) == 65816184


def test_parse_nvidia_smi_csv() -> None:
    gpus = parse_nvidia_smi_csv(SAMPLE_NVIDIA_SMI_CSV)
    assert len(gpus) == 2
    assert gpus[0] == GpuInfo(index=0, name="NVIDIA GeForce RTX 4090", vram_gb=24, driver="560.94")
    assert gpus[1].index == 1


def test_parse_nvidia_smi_csv_empty_returns_empty_list() -> None:
    assert parse_nvidia_smi_csv("") == []


def test_detect_cpu_uses_executor(tmp_path) -> None:
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text(SAMPLE_CPUINFO, encoding="utf-8")

    info = detect_cpu(read_text=lambda p: cpuinfo.read_text(encoding="utf-8"))

    assert info.model.startswith("AMD Ryzen 9 7950X")
    assert info.logical_cores == 2


def test_detect_ram_gb(tmp_path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       65816184 kB\n", encoding="utf-8")

    ram_gb = detect_ram_gb(read_text=lambda p: meminfo.read_text(encoding="utf-8"))

    # 65816184 kB / 1024 / 1024 ≈ 62.77 GB; round to 63
    assert 60 <= ram_gb <= 70


def test_detect_gpus_returns_empty_when_smi_missing() -> None:
    fake_run = lambda cmd, **kw: CommandResult(
        exit_code=-1, stdout="", stderr="", found=False, timed_out=False
    )
    assert detect_gpus(run_command=fake_run) == []


def test_detect_gpus_parses_csv_when_smi_present() -> None:
    fake_run = lambda cmd, **kw: CommandResult(
        exit_code=0, stdout=SAMPLE_NVIDIA_SMI_CSV, stderr="", found=True, timed_out=False
    )
    gpus = detect_gpus(run_command=fake_run)
    assert len(gpus) == 2


def test_detect_os_via_cmd_exe() -> None:
    fake_run = lambda cmd, **kw: CommandResult(
        exit_code=0,
        stdout="\nMicrosoft Windows [Version 10.0.22631.4111]\n",
        stderr="",
        found=True,
        timed_out=False,
    )
    info = detect_os(run_command=fake_run)
    assert "Windows" in info.description
    assert "22631" in info.description


def test_detect_wsl_reads_distro_and_kernel(tmp_path) -> None:
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="Ubuntu"\nVERSION_ID="22.04"\nPRETTY_NAME="Ubuntu 22.04.4 LTS"\n',
        encoding="utf-8",
    )

    fake_run = lambda cmd, **kw: CommandResult(
        exit_code=0,
        stdout="5.15.153.1-microsoft-standard-WSL2\n",
        stderr="",
        found=True,
        timed_out=False,
    )

    info = detect_wsl(
        read_text=lambda p: os_release.read_text(encoding="utf-8"),
        run_command=fake_run,
    )
    assert "Ubuntu 22.04" in info.distro
    assert "microsoft-standard-WSL2" in info.kernel
