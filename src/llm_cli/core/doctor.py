"""Load requirements.yaml and execute checks."""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml

from llm_cli.core import registry as _registry
from llm_cli.core.install_record import read_record
from llm_cli.core.params import evaluate_when
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
    scope: str | None = None


@dataclass(frozen=True)
class RequirementResult:
    requirement: Requirement
    status: CheckStatus
    detected_version: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class ScopeCheckResult:
    name: str
    status: str
    message: str


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
                scope=entry.get("scope"),
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


def _dashboard_scope_checks() -> list[ScopeCheckResult]:
    from llm_cli.core import dashboard as dash
    from llm_cli.core.versions import current_cli_version
    import shutil

    results: list[ScopeCheckResult] = []
    node = shutil.which("node")
    npm = shutil.which("npm")
    record = dash.load_installed_record()

    results.append(
        ScopeCheckResult(
            name="node",
            status="error" if (node is None and record is not None) else "info" if node is None else "ok",
            message="Node.js not found (install Node 20+)" if node is None else f"Found at {node}",
        )
    )
    results.append(
        ScopeCheckResult(
            name="npm",
            status="error" if (npm is None and record is not None) else "info" if npm is None else "ok",
            message="npm not found" if npm is None else f"Found at {npm}",
        )
    )
    results.append(
        ScopeCheckResult(
            name="dashboard installed",
            status="info" if record is None else "ok",
            message=(
                "Not installed (run `llm dashboard install`)"
                if record is None
                else f"Installed for CLI {record.cli_version} at {record.installed_at}"
            ),
        )
    )
    if record is not None:
        cur = current_cli_version()
        results.append(
            ScopeCheckResult(
                name="dashboard version matches CLI",
                status="ok" if record.cli_version == cur else "error",
                message=(
                    "Match"
                    if record.cli_version == cur
                    else f"Built for CLI {record.cli_version}, current is {cur}. "
                    "Run `llm dashboard install --reset`."
                ),
            )
        )
        verdict, reason = dash.verify_installed(cur)
        results.append(
            ScopeCheckResult(
                name="dashboard dist integrity",
                status="ok" if verdict == "ok" else "warning",
                message="OK" if verdict == "ok" else f"{verdict}: {reason}",
            )
        )

    try:
        pid = dash.read_server_pid()
    except RuntimeError:
        pid = None
    if pid is not None:
        alive = dash.is_server_alive(pid)
        results.append(
            ScopeCheckResult(
                name="dashboard server pid alive",
                status="ok" if alive else "warning",
                message=(
                    f"pid={pid} alive"
                    if alive
                    else f"Stale pid file (pid={pid}); run `llm dashboard stop`."
                ),
            )
        )

    results.append(_check_insecure_in_recent_log())
    return results


def _check_insecure_in_recent_log() -> ScopeCheckResult:
    from llm_cli.core import dashboard as dash

    log = dash.server_log_path()
    if not log.is_file():
        return ScopeCheckResult(
            name="dashboard last startup not --insecure",
            status="ok",
            message="No server.log present.",
        )
    tail = log.read_text(encoding="utf-8")[-4096:]
    matches = re.findall(r"\[SECURITY\].*", tail)
    if not matches:
        return ScopeCheckResult(
            name="dashboard last startup not --insecure",
            status="ok",
            message="No --insecure in recent startups.",
        )
    last = matches[-1]
    if "--insecure=True" in last:
        return ScopeCheckResult(
            name="dashboard last startup not --insecure",
            status="warning",
            message=(
                f"Last dashboard startup used --insecure: {last.strip()}. "
                "If unintentional, restart without --insecure."
            ),
        )
    return ScopeCheckResult(
        name="dashboard last startup not --insecure",
        status="ok",
        message="Last startup was localhost-only.",
    )


def _requirement_results_to_scope_checks(
    results: list[RequirementResult],
) -> list[ScopeCheckResult]:
    mapped: list[ScopeCheckResult] = []
    for result in results:
        if result.status == CheckStatus.OK:
            status = "ok"
        elif result.status in (CheckStatus.OUTDATED, CheckStatus.UNKNOWN):
            status = "warning"
        else:
            status = "error"

        message_bits: list[str] = []
        if result.detected_version:
            message_bits.append(f"detected={result.detected_version}")
        if result.detail:
            message_bits.append(result.detail)
        if not message_bits:
            message_bits.append("ok")

        mapped.append(
            ScopeCheckResult(
                name=result.requirement.id,
                status=status,
                message="; ".join(message_bits),
            )
        )
    return mapped


def run_scope(scope: str) -> list[ScopeCheckResult]:
    from llm_cli.core.scaffold import scaffold_root
    from llm_cli.core.settings import load_settings, resolve

    if scope == "default":
        reqs = [req for req in load_requirements(scaffold_root() / "requirements.yaml") if req.scope is None]
        return _requirement_results_to_scope_checks(check_all(reqs))
    if scope == "runtime":
        settings = resolve(load_settings())
        reqs = requirements_for_all_runtimes(
            scaffold_root(), settings.runtimes_dir, installed_only=True
        )
        return _requirement_results_to_scope_checks(check_all(reqs))
    if scope == "dashboard":
        return _dashboard_scope_checks()
    raise ValueError(f"unknown doctor scope: {scope}")


def _req_from_entry(entry: dict[str, Any], owner: str) -> Requirement | None:
    if "id" not in entry or "verify" not in entry:
        return None
    verify = entry["verify"]
    if not isinstance(verify, dict) or "cmd" not in verify or "version_regex" not in verify:
        return None
    return Requirement(
        id=str(entry["id"]),
        name=str(entry.get("name", entry["id"])),
        why=str(entry.get("why", f"required by {owner}")),
        verify_cmd=str(verify["cmd"]),
        version_regex=str(verify["version_regex"]),
        min_version=verify.get("min"),
        install_hint=str(entry.get("install_hint", "")),
    )


def requirements_for_runtime(
    repo: Path, runtime_id: str, *, build_params: dict[str, Any]
) -> list[Requirement]:
    """Return requirements declared by a single runtime, filtered by `when:` clauses."""
    mf = _registry.get_runtime_manifest(repo, runtime_id)
    if mf is None:
        return []

    out: list[Requirement] = []
    for entry in mf.requires:
        if not evaluate_when(entry.get("when"), build_params=build_params):
            continue
        req = _req_from_entry(entry, owner=runtime_id)
        if req is not None:
            out.append(req)
    return out


def _default_build_params(mf: _registry.RuntimeManifest) -> dict[str, Any]:
    del mf
    return {}


def requirements_for_all_runtimes(
    repo: Path, runtimes_dir: Path, *, installed_only: bool
) -> list[Requirement]:
    """Aggregate per-runtime requirements.

    Installed runtimes use their recorded build params. Uninstalled runtimes are
    included only for full sweeps, using build-schema defaults for `when:`.
    """
    out: list[Requirement] = []
    seen: set[str] = set()
    for mf in _registry.load_runtime_manifests(repo):
        rec = read_record(runtimes_dir, mf.id)
        if installed_only and rec is None:
            continue
        build_params = dict(rec.build_params) if rec is not None else _default_build_params(mf)
        for req in requirements_for_runtime(repo, mf.id, build_params=build_params):
            if req.id in seen:
                continue
            seen.add(req.id)
            out.append(req)
    return out


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


def _render_table(reqs: list[Requirement]) -> list[str]:
    lines = ["| ID | Name | Min | Verify | Install | Why |", "|---|---|---|---|---|---|"]
    for req in reqs:
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
    return lines


def render_requirements_md(requirements: list[Requirement]) -> str:
    """Render requirements.yaml to a Markdown table for human reading."""
    lines: list[str] = [_REQ_HEADER.rstrip(), ""]
    lines.extend(_render_table(requirements))
    return "\n".join(lines) + "\n"


def run_quick_checks() -> tuple[bool, str]:
    """Subset of doctor checks for post-update verify (spec §9.2 step 6).

    Returns ``(ok, detail)`` where *detail* is empty on success.
    """
    from llm_cli.core.scaffold import scaffold_root
    from llm_cli.core.settings import load_settings, resolve

    try:
        resolve(load_settings())
    except Exception as exc:  # noqa: BLE001
        return False, f"settings: {exc}"

    root = scaffold_root()
    if not root.is_dir():
        return False, f"scaffold root missing: {root}"

    req_path = scaffold_root() / "requirements.yaml"
    if not req_path.is_file():
        return False, f"requirements.yaml not readable at {req_path}"
    try:
        load_requirements(req_path)
    except Exception as exc:  # noqa: BLE001
        return False, f"requirements.yaml: {exc}"

    return True, ""


def render_requirements_md_grouped(
    universal: list[Requirement],
    by_runtime: dict[str, list[Requirement]],
    *,
    by_scope: dict[str, list[Requirement]] | None = None,
) -> str:
    """Render universal requirements plus optional scope and per-runtime sections."""
    lines: list[str] = [_REQ_HEADER.rstrip(), "", "## Universal", ""]
    lines.extend(_render_table(universal))
    for scope_id in sorted(by_scope or {}):
        lines.extend(["", f"## Scope: {scope_id}", ""])
        lines.extend(_render_table(by_scope[scope_id]))
    for runtime_id in sorted(by_runtime):
        lines.extend(["", f"## Runtime: {runtime_id}", ""])
        lines.extend(_render_table(by_runtime[runtime_id]))
    return "\n".join(lines) + "\n"
