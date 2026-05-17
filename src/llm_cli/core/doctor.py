"""Load requirements.yaml and execute checks."""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

import yaml

from llm_cli.core.shell import CommandResult, run_command as _real_run_command
from llm_cli.core.versions import compare_versions

RunCommand = Callable[..., CommandResult]


class CheckStatus(str, Enum):
    OK = "ok"
    OUTDATED = "outdated"
    MISSING = "missing"
    UNKNOWN = "unknown"  # cmd ran but version couldn't be parsed
    ERROR = "error"  # cmd ran with nonzero exit


@dataclass(frozen=True)
class Requirement:
    id: str
    name: str
    why: str
    verify_cmd: str
    version_regex: str
    min_version: str | None
    install_hint: str


@dataclass(frozen=True)
class RequirementResult:
    requirement: Requirement
    status: CheckStatus
    detected_version: str | None = None
    detail: str = ""


def load_requirements(path: Path) -> list[Requirement]:
    """Load requirements.yaml into a list of Requirement objects."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError("requirements.yaml must be a top-level list")

    out: list[Requirement] = []
    for entry in raw:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        verify = entry.get("verify", {})
        if not isinstance(verify, dict):
            continue
        out.append(
            Requirement(
                id=str(entry["id"]),
                name=str(entry.get("name", entry["id"])),
                why=str(entry.get("why", "")),
                verify_cmd=str(verify["cmd"]),
                version_regex=str(verify["version_regex"]),
                min_version=verify.get("min"),
                install_hint=str(entry.get("install_hint", "")),
            )
        )
    return out


def check_requirement(
    req: Requirement,
    *,
    run_command: RunCommand = _real_run_command,
) -> RequirementResult:
    """Execute a single requirement's verify command and classify the result."""
    cmd_parts = shlex.split(req.verify_cmd, posix=False)
    result = run_command(cmd_parts, timeout_sec=8.0)

    if not result.found:
        return RequirementResult(
            requirement=req, status=CheckStatus.MISSING, detail="executable not on PATH"
        )

    if result.exit_code != 0:
        return RequirementResult(
            requirement=req,
            status=CheckStatus.ERROR,
            detail=f"exit {result.exit_code}: {result.stderr.strip() or result.stdout.strip()}",
        )

    combined = result.stdout + "\n" + result.stderr
    match = re.search(req.version_regex, combined)
    if not match:
        return RequirementResult(
            requirement=req,
            status=CheckStatus.UNKNOWN,
            detail="version_regex did not match command output",
        )

    detected = match.group(1) if match.lastindex else match.group(0)

    if req.min_version is None:
        return RequirementResult(requirement=req, status=CheckStatus.OK, detected_version=detected)

    cmp = compare_versions(detected, req.min_version)
    if cmp >= 0:
        return RequirementResult(requirement=req, status=CheckStatus.OK, detected_version=detected)
    return RequirementResult(
        requirement=req,
        status=CheckStatus.OUTDATED,
        detected_version=detected,
        detail=f"need >= {req.min_version}",
    )


def check_all(
    requirements: list[Requirement],
    *,
    run_command: RunCommand = _real_run_command,
) -> list[RequirementResult]:
    return [check_requirement(r, run_command=run_command) for r in requirements]


def systemd_linger_advisory(
    *,
    run_command: RunCommand = _real_run_command,
) -> str | None:
    """Return a warning message if user lingering is off; None if OK or not applicable.

    User systemd units (e.g. ``llm serve --systemd``) keep running after logout only
    when lingering is enabled. Missing ``loginctl`` or unexpected output is ignored.
    """
    result = run_command(
        ["loginctl", "show-user", "--property=Linger"],
        timeout_sec=6.0,
    )
    if not result.found or result.timed_out or result.exit_code != 0:
        return None
    line = (result.stdout or "").strip()
    if line == "Linger=yes":
        return None
    if line == "Linger=no":
        return (
            "User systemd services stop at logout unless lingering is enabled "
            "(sudo loginctl enable-linger $USER)."
        )
    return None


# ---------- requirements.md rendering ----------

_REQ_HEADER = (
    "# External Requirements\n\n"
    "<!-- AUTO-GENERATED from requirements.yaml — do not edit by hand. "
    "Run `llm doctor render-requirements` to regenerate. -->\n\n"
    "These prerequisites must exist on the machine for the LocalLLM CLI and the "
    "runtimes' build/serve scripts to function. Run `llm doctor` to verify the "
    "current state of each.\n\n"
)


def _escape_pipes(text: str) -> str:
    return text.replace("|", "\\|")


def render_requirements_md(requirements: list[Requirement]) -> str:
    """Render requirements.yaml to a Markdown table for human reading."""
    lines: list[str] = [_REQ_HEADER.rstrip(), ""]
    lines.append("| ID | Name | Min | Verify | Install | Why |")
    lines.append("|---|---|---|---|---|---|")
    for req in requirements:
        min_v = req.min_version if req.min_version else "—"
        lines.append(
            "| {id} | {name} | {min} | `{verify}` | {install} | {why} |".format(
                id=_escape_pipes(req.id),
                name=_escape_pipes(req.name),
                min=_escape_pipes(min_v),
                verify=_escape_pipes(req.verify_cmd),
                install=_escape_pipes(req.install_hint),
                why=_escape_pipes(req.why),
            )
        )
    return "\n".join(lines) + "\n"
