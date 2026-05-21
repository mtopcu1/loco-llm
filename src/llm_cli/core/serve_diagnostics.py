"""Build actionable messages when serve/switch exits without a ServeError."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core import registry
from llm_cli.core.install_record import is_installed
from llm_cli.core.lifecycle import logs_dir, read_running, state_root
from llm_cli.core.model_registry import get_entry as registry_model_entry
from llm_cli.core.serve_spawn import port_in_use
from llm_cli.core.settings import load_settings, resolve


def tail_serve_log(log_path: Path, *, max_lines: int = 30) -> list[str]:
    if not log_path.is_file():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-max_lines:] if lines else []


def diagnose_serve_failure(config_id: str, *, exit_code: int = 1) -> str:
    """Best-effort explanation when only typer.Exit(exit_code) is known."""
    settings = resolve(load_settings())
    state_base = state_root(settings)
    log_path = logs_dir(state_base) / f"{config_id}.log"
    parts: list[str] = [f"serve/switch exited with code {exit_code}"]

    cfg = registry.get_config_merged(config_id)
    if cfg is None:
        parts.append(f"config {config_id!r} not found")
    else:
        runtime_id = str(cfg.data.get("runtime", ""))
        if runtime_id and not is_installed(settings.runtimes_dir, runtime_id):
            parts.append(
                f"runtime {runtime_id!r} is not installed "
                f"(run: loco runtime install {runtime_id})"
            )
        model_id = cfg.data.get("model")
        if isinstance(model_id, str):
            if registry_model_entry(settings.models_dir, model_id) is None:
                parts.append(f"model {model_id!r} is not in the model registry")
        serve = cfg.data.get("serve") if isinstance(cfg.data.get("serve"), dict) else {}
        host = serve.get("host")
        port = serve.get("port")
        if host is not None and port is not None:
            try:
                if port_in_use(str(host), int(port)):
                    parts.append(f"port {port} on {host} is already in use")
            except (TypeError, ValueError):
                pass

    rec = read_running(state_base)
    if rec is not None and rec.config_id != config_id:
        parts.append(
            f"another config is running ({rec.config_id}); stop it or use loco switch"
        )

    parts.append(f"serve log: {log_path}")
    tail = tail_serve_log(log_path)
    if tail:
        parts.append("last log lines:")
        parts.extend(tail[-18:])
    else:
        parts.append(
            "(no serve log yet — failure likely before serve.sh wrote output; "
            "run `loco serve <config>` in a terminal)"
        )
    parts.append(f"terminal: loco serve {config_id}")
    parts.append("diagnostics: loco doctor")
    return "\n".join(parts)
