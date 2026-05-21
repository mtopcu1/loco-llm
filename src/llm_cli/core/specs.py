"""Hardware and environment detection for `loco specs`.

Detection functions accept injected `read_text` and `run_command` callables
so tests can substitute fakes. Each detector degrades gracefully — missing
tools yield "not detected" markers instead of exceptions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from llm_cli.core.shell import CommandResult, run_command as _real_run_command

NOT_DETECTED = "not detected"

ReadText = Callable[[Path | str], str]
RunCommand = Callable[..., CommandResult]


def _default_read_text(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")


@dataclass(frozen=True)
class CpuInfo:
    model: str
    logical_cores: int


@dataclass(frozen=True)
class GpuInfo:
    index: int
    name: str
    vram_gb: int
    driver: str


@dataclass(frozen=True)
class OsInfo:
    description: str


@dataclass(frozen=True)
class WslInfo:
    distro: str
    kernel: str


@dataclass(frozen=True)
class SystemSpecs:
    cpu: CpuInfo
    ram_gb: int
    gpus: list[GpuInfo] = field(default_factory=list)
    cuda_runtime: str = NOT_DETECTED
    os: OsInfo = OsInfo(description=NOT_DETECTED)
    wsl: WslInfo = WslInfo(distro=NOT_DETECTED, kernel=NOT_DETECTED)
    systemd_enabled: bool = False
    repo_root: str = NOT_DETECTED
    data_root: str = NOT_DETECTED


# ---------- parsers (pure functions over strings) ----------


def parse_proc_cpuinfo(text: str) -> CpuInfo:
    if not text.strip():
        raise ValueError("empty /proc/cpuinfo")

    model_match = re.search(r"^model name\s*:\s*(.+)$", text, re.MULTILINE)
    if not model_match:
        raise ValueError("model name not found in /proc/cpuinfo")
    model = model_match.group(1).strip()

    logical_cores = len(re.findall(r"^processor\s*:", text, re.MULTILINE))
    return CpuInfo(model=model, logical_cores=logical_cores)


def parse_meminfo_total_kb(text: str) -> int:
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB", text, re.MULTILINE)
    if not match:
        raise ValueError("MemTotal not found in /proc/meminfo")
    return int(match.group(1))


def parse_nvidia_smi_csv(text: str) -> list[GpuInfo]:
    gpus: list[GpuInfo] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        idx_s, name, vram_s, driver = parts[0], parts[1], parts[2], parts[3]
        try:
            idx = int(idx_s)
        except ValueError:
            continue
        vram_match = re.search(r"(\d+)", vram_s)
        if not vram_match:
            continue
        vram_mib = int(vram_match.group(1))
        vram_gb = round(vram_mib / 1024)
        gpus.append(GpuInfo(index=idx, name=name, vram_gb=vram_gb, driver=driver))
    return gpus


# ---------- detectors (use injected IO) ----------


def detect_cpu(read_text: ReadText = _default_read_text) -> CpuInfo:
    try:
        return parse_proc_cpuinfo(read_text("/proc/cpuinfo"))
    except (FileNotFoundError, OSError, ValueError):
        return CpuInfo(model=NOT_DETECTED, logical_cores=0)


def detect_ram_gb(read_text: ReadText = _default_read_text) -> int:
    try:
        kb = parse_meminfo_total_kb(read_text("/proc/meminfo"))
        return round(kb / 1024 / 1024)
    except (FileNotFoundError, OSError, ValueError):
        return 0


def detect_gpus(run_command: RunCommand = _real_run_command) -> list[GpuInfo]:
    result = run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,driver_version",
            "--format=csv,noheader",
        ],
        timeout_sec=5.0,
    )
    if not result.found or result.exit_code != 0:
        return []
    return parse_nvidia_smi_csv(result.stdout)


def detect_cuda_runtime(run_command: RunCommand = _real_run_command) -> str:
    """Best-effort CUDA runtime version from `nvidia-smi`."""
    result = run_command(["nvidia-smi"], timeout_sec=5.0)
    if not result.found or result.exit_code != 0:
        return NOT_DETECTED
    match = re.search(r"CUDA Version:\s*([\d.]+)", result.stdout)
    return match.group(1) if match else NOT_DETECTED


def detect_os(run_command: RunCommand = _real_run_command) -> OsInfo:
    """Read Windows version via WSL interop (`cmd.exe /c ver`)."""
    result = run_command(["cmd.exe", "/c", "ver"], timeout_sec=5.0)
    if not result.found or result.exit_code != 0:
        return OsInfo(description=NOT_DETECTED)
    description = (
        result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else NOT_DETECTED
    )
    return OsInfo(description=description)


def detect_wsl(
    read_text: ReadText = _default_read_text,
    run_command: RunCommand = _real_run_command,
) -> WslInfo:
    distro = NOT_DETECTED
    try:
        os_release = read_text("/etc/os-release")
        match = re.search(r'^PRETTY_NAME="?(.+?)"?$', os_release, re.MULTILINE)
        if match:
            distro = match.group(1).strip()
    except (FileNotFoundError, OSError):
        pass

    kernel = NOT_DETECTED
    result = run_command(["uname", "-r"], timeout_sec=2.0)
    if result.found and result.exit_code == 0:
        kernel = result.stdout.strip()

    return WslInfo(distro=distro, kernel=kernel)


def detect_systemd(
    read_text: ReadText = _default_read_text,
    run_command: RunCommand = _real_run_command,
) -> bool:
    """Return True if WSL has systemd enabled."""
    try:
        wsl_conf = read_text("/etc/wsl.conf")
        if re.search(r"^\s*systemd\s*=\s*true", wsl_conf, re.MULTILINE | re.IGNORECASE):
            result = run_command(["systemctl", "is-system-running"], timeout_sec=3.0)
            return result.found and result.exit_code in (0, 1)  # 1 = degraded; still systemd
    except (FileNotFoundError, OSError):
        pass
    return False


def detect_all(
    read_text: ReadText = _default_read_text,
    run_command: RunCommand = _real_run_command,
    *,
    repo_root: str = NOT_DETECTED,
    data_root: str = NOT_DETECTED,
) -> SystemSpecs:
    """Collect everything detectable into a SystemSpecs."""
    return SystemSpecs(
        cpu=detect_cpu(read_text),
        ram_gb=detect_ram_gb(read_text),
        gpus=detect_gpus(run_command),
        cuda_runtime=detect_cuda_runtime(run_command),
        os=detect_os(run_command),
        wsl=detect_wsl(read_text, run_command),
        systemd_enabled=detect_systemd(read_text, run_command),
        repo_root=repo_root,
        data_root=data_root,
    )


# ---------- rendering ----------


def render_specs_block(specs: SystemSpecs, *, generated_at: str) -> str:
    """Render the inner specs block (no surrounding markers, no notes section)."""
    lines: list[str] = []
    lines.append(f"_Generated: {generated_at}_")
    lines.append("")
    lines.append("## Host")
    lines.append(f"- **OS:** {specs.os.description}")
    lines.append(f"- **CPU:** {specs.cpu.model} ({specs.cpu.logical_cores} logical cores)")
    lines.append(f"- **RAM:** {specs.ram_gb} GB")
    lines.append("")
    lines.append("## GPU")
    if specs.gpus:
        lines.append("| Idx | Name | VRAM | Driver |")
        lines.append("|---|---|---|---|")
        for gpu in specs.gpus:
            lines.append(f"| {gpu.index} | {gpu.name} | {gpu.vram_gb} GB | {gpu.driver} |")
    else:
        lines.append("_No GPU detected._")
    lines.append("")
    lines.append(f"CUDA runtime: {specs.cuda_runtime}")
    lines.append("")
    lines.append("## WSL")
    lines.append(f"- **Distro:** {specs.wsl.distro}")
    lines.append(f"- **Kernel:** {specs.wsl.kernel}")
    systemd_label = "enabled" if specs.systemd_enabled else "disabled"
    lines.append(f"- **Systemd:** {systemd_label}")
    lines.append("")
    lines.append("## Storage layout")
    lines.append(f"- Repo: `{specs.repo_root}`")
    lines.append(f"- Data root: `{specs.data_root}`")
    return "\n".join(lines)


# ---------- marker handling ----------

SPECS_START_MARKER = "<!-- llm:specs:start -->"
SPECS_END_MARKER = "<!-- llm:specs:end -->"

_AUTOGEN_HEADER_COMMENT = (
    "<!-- AUTO-GENERATED: do not edit between markers. "
    "Run `loco specs` to regenerate. -->"
)


class MarkersMissingError(RuntimeError):
    """Raised when specs.md does not contain the expected markers."""


def _scaffold_with_markers(block: str) -> str:
    return (
        "# System Specs\n\n"
        f"{_AUTOGEN_HEADER_COMMENT}\n"
        f"{SPECS_START_MARKER}\n"
        f"{block}\n"
        f"{SPECS_END_MARKER}\n\n"
        "## Notes\n"
        "<!-- Free-form. Preserved across regenerations. -->\n"
    )


def update_specs_markdown(existing: str, new_block: str, *, force: bool = False) -> str:
    """Replace the contents between markers with new_block.

    Returns the updated text. Raises MarkersMissingError if markers are
    missing and force=False; if force=True, replaces the entire file with
    a scaffold containing the new block.
    """
    start_idx = existing.find(SPECS_START_MARKER)
    end_idx = existing.find(SPECS_END_MARKER)

    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        if not force:
            raise MarkersMissingError(
                "specs.md is missing the llm:specs markers; pass force=True to overwrite."
            )
        return _scaffold_with_markers(new_block)

    head = existing[: start_idx + len(SPECS_START_MARKER)]
    tail = existing[end_idx:]
    return f"{head}\n{new_block}\n{tail}"
