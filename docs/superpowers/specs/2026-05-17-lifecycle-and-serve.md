# LocalLLM Lifecycle & Serve Design

_Date: 2026-05-17_
_Status: Approved by user, ready for implementation planning_

## 1. Purpose

Add the runtime-lifecycle slice of the CLI: serve any config in one of three modes (foreground / background / systemd), stop it, switch to another config in the same mode, see what's running, and tail logs. No "daily driver" pin — the currently-running config is the active state.

## 2. Problems solved

After Milestone 1 + the settings redesign, the CLI can build runtimes, pull models, and list/validate configs, but it cannot **start a server**. There's no way to run a chosen config, no way to know what's running, no way to switch configs without manual `kill`/`bash`/`systemctl` invocations.

## 3. Goals

- One verb (`loco serve <config>`) that works in three modes via flags.
- A single `loco status` that tells the truth across all three modes.
- A single `loco switch <config>` that preserves the active mode.
- A single managed systemd unit (`loco.service`), rewritten per config — no "default config pin," no `active.yaml`.
- `loco stop` and `loco logs` that don't care which mode is active.
- All `state/` files gitignored — none of this state is part of the repo.

## 4. Non-goals

- **No multi-service support.** At most one server runs at a time, regardless of mode. (Future: relax this if needed.)
- **No custom systemd unit management.** Power users with hand-written units run `systemctl` themselves; the CLI knows about exactly one unit: `loco.service`.
- **No daily-driver pin.** `state/active.yaml` is not introduced. `loco default` is not introduced.
- **No log rotation.** Per-session append for now; cleanup is `rm`.
- **No `loco bench` / `loco results`.** Out of scope; separate spec.

## 5. Architecture

### 5.1 Command surface

```text
loco serve <config>                      # background (default); waits for ready; returns
loco serve <config> --foreground         # attached to terminal; tracked in state/running.json
loco serve <config> --systemd            # binds loco.service to <config>; waits for ready; returns

loco stop                                # stops whatever is running (mode-aware)
loco switch <config>                     # stop current + start <config> in the same mode
loco status [--json]                     # not running | mode + config + port + uptime
loco logs [--follow|-f] [--lines|-n N]   # mode-aware tail
```

- `--foreground` / `--systemd` are mutually exclusive (and both implicitly negate "background").
- `loco switch` while in foreground mode errors with: "Foreground sessions can't be switched; Ctrl-C in the original terminal and rerun `loco serve <new>`."

### 5.2 State files

| Path | Format | Writer | Reader | Notes |
|---|---|---|---|---|
| `state/running.json` | JSON object | `loco serve` (all modes), cleared by `loco stop` and by foreground's SIGINT trap | `loco status`, `loco stop`, `loco switch`, `loco logs` | At most one record; missing/empty file = nothing running |
| `state/logs/<config-id>.log` | text, per-session append with timestamped header | `loco serve` fg+bg (stderr+stdout) | `loco logs` (file modes), human `tail` | Not written for systemd mode (use journalctl) |
| `state/history.jsonl` | one JSON object per line | every lifecycle command | future UI; humans | Append-only |
| `~/.config/systemd/user/loco.service` | INI unit file | `loco serve <cfg> --systemd` | systemd | Rewritten per config; survives `loco stop` |

All four paths are **gitignored**. Add `state/running.json`, `state/logs/`, `state/history.jsonl` to `.gitignore` (the systemd path is outside the repo).

`state/running.json` shape (one of, depending on mode):

```json
{ "mode": "foreground", "config_id": "...", "pid": 12345, "port": 8000,
  "started_at": "2026-05-17T16:00:00Z", "log_path": "state/logs/<id>.log" }
```
```json
{ "mode": "background", "config_id": "...", "pid": 12345, "port": 8000,
  "started_at": "...", "log_path": "state/logs/<id>.log" }
```
```json
{ "mode": "systemd", "config_id": "...", "unit": "loco.service", "port": 8000,
  "started_at": "..." }
```

`state/history.jsonl` event examples:

```json
{ "ts": "...", "action": "start",   "mode": "background", "config_id": "..." }
{ "ts": "...", "action": "stop",    "mode": "background", "config_id": "..." }
{ "ts": "...", "action": "switch",  "mode": "systemd",    "from": "...", "to": "..." }
{ "ts": "...", "action": "systemd-write", "unit": "loco.service", "config_id": "..." }
{ "ts": "...", "action": "reap-stale", "reason": "pid-gone", "config_id": "..." }
```

### 5.3 Truth model

- **fg, bg:** `running.json` is the truth. We sanity-check by `kill -0 <pid>` on `loco status` / before `loco stop`; if the PID is dead, we clear `running.json` (and log a `reap-stale` event).
- **systemd:** `systemctl --user is-active loco.service` is the truth. `running.json` is a convenience cache; if `is-active` says inactive but we have a systemd-mode `running.json`, we clear the cache.
- A `loco serve <other>` while another is live → reject with a clear hint to use `loco switch` or `loco stop`.

### 5.4 Per-mode mechanics

| Concern | `--foreground` | (default) background | `--systemd` |
|---|---|---|---|
| Spawn | `wsl bash -lc '<env>; cd <repo>; exec runtimes/<rt>/serve.sh --config <cfg>'` in CLI's process group; SIGINT trap clears `running.json` and forwards SIGTERM | `wsl bash -lc 'nohup ... </dev/null >>LOG 2>&1 &'`, capture child PID via `wait` + `$!` echo trick | (re)write `~/.config/systemd/user/loco.service`; `systemctl --user daemon-reload` (only if file changed); `systemctl --user restart loco.service` |
| Wait for ready | no (output streams) | yes — poll `runtimes/<rt>/healthcheck.sh --config <cfg>` every 1s until exit 0 or `serve.readiness.timeout_seconds` (default 600s) | yes — same poll **plus** `systemctl --user is-active` must be `active` |
| Writes `running.json` | yes (on spawn) | yes (after readiness) | yes (after readiness) |
| Logs go to | `state/logs/<id>.log` AND user's terminal (tee via bash `\| tee -a`) | `state/logs/<id>.log` only | journald (via systemd) |
| `loco logs` impl | `tail -n N -f? state/logs/<id>.log` | same | `journalctl --user -u loco.service -n N [-f]` |
| `loco stop` | `kill -TERM <pid>`; wait up to 10s; `kill -KILL` if still alive; clear `running.json` | same | `systemctl --user stop loco.service`; clear `running.json` |

`LLM_*` env vars are injected into bash for fg+bg via the existing `run_repo_bash` mechanism (data_root, repo_root, runtimes, models, cache). The systemd unit's `ExecStart` re-enters the CLI, which then injects them itself when spawning serve.sh.

### 5.5 Systemd unit body (template)

Rewritten on every `loco serve <cfg> --systemd` (or skipped if byte-identical to what we'd write):

```ini
# AUTO-GENERATED by `loco serve`. Edit will be overwritten on next `loco serve --systemd`.
[Unit]
Description=LocalLLM service (config: <CONFIG_ID>)
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/loco serve <CONFIG_ID> --foreground-from-supervisor
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

`--foreground-from-supervisor` is an **internal, hidden** flag:

- Same as `--foreground` in process model (exec, attach to current process), **but** does not write `state/running.json` (the parent `loco serve --systemd` invocation already did).
- Does not tee to a log file (systemd captures stdout/stderr).
- Does not register a SIGINT trap (systemd handles signal forwarding).
- Hidden from `loco --help` (`hidden=True` on the Typer option).

Linger is not auto-enabled. `loco doctor` grows a `systemd-linger` check that runs `loginctl show-user --property=Linger` and warns if absent; install hint is `sudo loginctl enable-linger $USER`.

### 5.6 Readiness probe

`runtimes/<id>/healthcheck.sh --config <cfg>` is the existing contract: exit 0 = ready. Poll interval 1s, timeout from `cfg.readiness.timeout_seconds` (default 600). On timeout:

- Background mode: SIGTERM the child, surface tail of `state/logs/<id>.log`, exit nonzero.
- Systemd mode: `systemctl --user stop loco.service`, suggest `journalctl --user -u loco.service -n 50`.

### 5.7 Port-in-use check

Before spawning (any mode), `socket.bind(('127.0.0.1', cfg.serve.port))` probe. If bind fails (EADDRINUSE), fail fast with: `port <N> is already in use; another process holds it.` This catches accidental external collisions early.

### 5.8 `loco status` (text)

Two outputs only:

```text
status: not running
```

or:

```text
status: running
mode:   background
config: vllm-cuda__qwen2-7b-instruct__default
port:   8000
pid:    12345
uptime: 2h 14m
log:    state/logs/vllm-cuda__qwen2-7b-instruct__default.log
```

(`mode: systemd` swaps `pid:` for `unit: loco.service` and `log:` for `journalctl: journalctl --user -u loco.service`.)

`--json` returns the underlying `running.json` plus a derived `uptime_seconds` and (for fg/bg) a `pid_alive` boolean.

Exit code: 0 whether or not anything is running (it's a query). 

### 5.9 Edge-case semantics

| Situation | Behavior |
|---|---|
| `loco stop` when nothing is running | Exit 0, print `nothing running`. (Idempotent stop.) |
| `loco switch <cfg>` when nothing is running | Exit 1, `nothing running; use \`loco serve <cfg>\` instead`. |
| `loco logs` when nothing is running | Exit 1, `nothing running`. |
| `loco serve <cfg>` when same config already live in any mode | Exit 1, `<cfg> already running in <mode>; use \`loco switch\` to change config or \`loco stop\` first`. |
| `loco serve <cfg> --systemd` when same config already systemd-active **and** unit byte-identical | No-op success: `already serving <cfg> via systemd`. No restart. |
| `loco switch <cfg>` to the **same** config | Behaves as a restart (stop + start the same config). Useful after editing the config file. |

## 6. Module/file layout

| Path | Role |
|---|---|
| `src/llm_cli/core/lifecycle.py` | `LifecycleState` (in-memory record), `read_running()` / `write_running()` / `clear_running()`, `append_history(event)`, `is_alive(pid)`, `reconcile()` (clears stale fg/bg/systemd entries). |
| `src/llm_cli/core/serve_spawn.py` | `spawn_foreground(...)`, `spawn_background(...)`, `wait_for_ready(...)`, port probe, `bash` invocation builders. Pure functions over `Settings` + resolved config. |
| `src/llm_cli/core/systemd_unit.py` | Template render, `desired_unit_text(config_id)`, `read_existing_unit(path)`, `write_if_different(...)`, `daemon_reload()`, `restart_unit()`, `stop_unit()`, `is_active(unit)`. Shell calls live here. |
| `src/llm_cli/commands/serve.py` | `loco serve`, `loco switch`. Dispatches to fg/bg/systemd. |
| `src/llm_cli/commands/lifecycle_cmds.py` | `loco stop`, `loco status`, `loco logs`. |
| `state/` | runtime state (gitignored) — created on first use. |

## 7. Testing

### 7.1 Unit

- `lifecycle.py`: `running.json` round-trip; `is_alive(pid)` (use `os.getpid()` and a dead PID); `reconcile()` clears a stale record when PID is dead.
- `serve_spawn.py`: builder produces correct bash (snapshot test); `wait_for_ready` with a fake healthcheck that flips after N calls; port-in-use probe.
- `systemd_unit.py`: template render is deterministic; `write_if_different` is a no-op when bytes match; shell calls are exercised through a `subprocess.run` fake.

### 7.2 Integration (against `stub-runtime`)

The existing `stub-runtime/serve.sh` exits 1 — we replace it with a real toy server: a Python one-liner via bash that opens a TCP socket on the chosen port and writes "hello" to anyone who connects, plus a `healthcheck.sh` that succeeds when the port is connectable. This satisfies the runtime contract and is fast in tests.

- `loco serve <cfg>` (bg) against stub-runtime: returns within readiness window, `loco status` shows `mode: background`, then `loco stop` terminates.
- `loco serve <cfg> --foreground` started in a subprocess thread; `loco status` from another invocation sees it; `loco stop` clears it.
- `loco switch` in bg: stop+start happens; new config in `running.json`.
- Conflict: `loco serve` when one is up → exit 1, hint.
- Port collision: pre-bind the port in the test, `loco serve` fails fast.
- `loco logs -n 5` reads tail of the right file.

### 7.3 Systemd (gated)

- A `pytest.mark.systemd` marker; tests skip unless `systemctl --user list-units --no-pager` works (CI default: skipped).
- When enabled: write unit, start, status, restart with new config (unit byte-diff detected), stop, verify unit not deleted.

### 7.4 Mock vs real

Spawning real bash subprocesses in unit tests is brittle on Windows. The plan:

- `serve_spawn.spawn_*` functions take an injectable `runner` callable (default `subprocess.Popen`). Unit tests substitute a fake.
- Integration tests run under WSL only (skip on pure-Windows pytest); detected via `os.name`.

## 8. Documentation updates

- New: `docs/lifecycle.md` — mode comparison table, "how to choose a mode," `loco switch` semantics, troubleshooting (port in use, healthcheck timeout, systemd linger).
- `README.md` — extend CLI commands table with `serve / stop / switch / status / logs`. Update Getting Started: add a one-liner `loco serve stub-runtime__stub-model__default` smoke step.
- `docs/repo-conventions.md` — add `state/` row; clarify that `state/` is gitignored runtime data and not configuration.
- `docs/add-a-runtime.md` — add a section on healthcheck.sh contract (exit 0 = ready, called repeatedly) and serve.sh signal handling (SIGTERM must shut down cleanly).
- `docs/superpowers/specs/2026-05-15-localllm-scaffolding-design.md` — add a note at the top: "Lifecycle commands are designed in [2026-05-17-lifecycle-and-serve.md](2026-05-17-lifecycle-and-serve.md); they replace the original sections 7.2/7.3 — no `state/active.yaml`, no `loco default`, single managed systemd unit."

## 9. Open / deferred

- **Multiple concurrent services.** Tracked as future work; `running.json` becomes an array, `serve` accepts a `--name` to disambiguate, `stop`/`logs`/`status` take a `--name` or default to the only one running.
- **Log rotation.** Add when the file becomes a pain in practice.
- **`loco history`.** `state/history.jsonl` is written but not exposed via CLI yet. Add when there's something to read it for (a UI).
- **`loco restart`.** Not added; `loco switch` to the same config covers it.
- **Hot reload of configs.** No — change a config, then `loco switch <cfg>` (rewrites unit if systemd, restarts otherwise).
