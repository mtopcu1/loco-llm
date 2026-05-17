# Lifecycle: serve, stop, switch, status, logs

This matches the CLI behavior described in
[`superpowers/specs/2026-05-17-lifecycle-and-serve.md`](superpowers/specs/2026-05-17-lifecycle-and-serve.md).

## Commands

| Command | Role |
|---|---|
| `llm serve <config>` | Start in **background** (default): spawns the runtime’s `serve.sh`, waits until `healthcheck.sh` exits 0, then records state. |
| `llm serve <config> --foreground` | Same process attached to your terminal; output is teed to `state/logs/<config-id>.log`. |
| `llm serve <config> --systemd` | Rewrite `~/.config/systemd/user/llm.service` for this config, restart the unit, wait until active + healthy. |
| `llm switch <config>` | Stop the current service and start `<config>` in the **same** mode (not allowed in foreground). |
| `llm stop` | Stop whatever is running (SIGTERM/KILL for fg/bg, `systemctl --user stop` for systemd). |
| `llm status [--json]` | Query `state/running.json` and reconcile stale entries. |
| `llm logs [-f] [-n N]` | Tail file logs (fg/bg) or `journalctl --user -u llm.service` (systemd). |

There is **no** separate “daily driver” pin: the running service is the active state.

## Choosing a mode

| Mode | Best when |
|---|---|
| Background | Normal use from an interactive shell; logs in `state/logs/`. |
| Foreground | Debugging; you want live output and Ctrl+C semantics. |
| systemd | Service should survive closing the terminal — use with **user lingering** (`llm doctor` warns if `Linger=no`). |

## Readiness

Before any spawn, the CLI checks **`${LLM_RUNTIMES}/<runtime-id>/.installed`** (equivalently the resolved runtimes dir from settings). If that marker is absent, **`llm serve`** and **`llm switch`** refuse with a hint to run **`llm runtime install <id>`**.

After spawn, the CLI polls `runtimes/<runtime-id>/healthcheck.sh` about once per second until it exits **0** or `readiness.timeout_seconds` in the config elapses (default 600). Runtimes should treat exit 0 as “ready to accept traffic.”

## Troubleshooting

- **Port in use** — Another process is bound to `serve.port`. Stop it or change the config port.
- **Readiness timeout** — Check `state/logs/<id>.log` (bg/fg) or `journalctl --user -u llm.service -n 50` (systemd).
- **systemd stops after logout** — Enable lingering: `sudo loginctl enable-linger $USER`.

State under `state/` is machine-local and gitignored; see [`repo-conventions.md`](repo-conventions.md).
