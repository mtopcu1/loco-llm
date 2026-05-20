# LocalLLM Web Dashboard Design

_Date: 2026-05-20_
_Status: Approved by user, ready for implementation planning_

## 1. Purpose

Add a single-user, locally-hosted web dashboard for managing every aspect of the LocalLLM CLI installation. The dashboard is an opt-in install, shipped in-source and built locally, that exposes the existing CLI's functionality (and a handful of new affordances) through a React SPA on top of a FastAPI backend.

Goal: turn "tab back to the terminal to manage runtimes / models / configs / instances" into "stay in one browser tab".

## 2. Goals

- **Cover the CLI** — every routine operation a power user does with the CLI is reachable from the dashboard: install runtimes, pull models, author configs (with rich param editing), serve them, monitor them, and inspect history.
- **Stay a control plane** — same discipline as the CLI: the dashboard never holds canonical state; it reads and writes the same files (`configs/*.yaml`, `runtimes/<id>/.installed`, `state/*`, `~/.config/llm/config.yaml`) via the same `llm_cli.core.*` functions the CLI calls.
- **Localhost-first** — bound to `127.0.0.1` by default. LAN exposure requires friction (`--insecure --i-understand --allowed-host …`) and is loudly warned about everywhere.
- **Opt-in toolchain** — Node + FastAPI are extras, gated behind `llm dashboard install`. Users who only want the CLI never see them.
- **Mirror existing patterns** — `install` writes a `.installed` marker; `doctor` gains a `dashboard` scope; `setup` gets an opt-in step; `update` opportunistically rebuilds.

## 3. Non-goals

- **No multi-user, no authentication in v1.** Localhost-only single-user. Adding auth is v2 work, gated on real LAN scenarios materializing.
- **No multi-instance support.** Inherits the single-running-config constraint from the lifecycle spec.
- **No playground / chat tab in v1.** Dashboard is for *management*; talking to the model stays in the user's preferred OpenAI client.
- **No benchmarks UI in v1.** `benchmarks/` exists but earns its own spec + plan.
- **No historical time-series charts in v1.** Live numbers + sparkline (last 60 snapshots) + simple aggregates only.
- **No persistent job survival across dashboard restart.** Jobs die with the dashboard server (subprocess SIGTERMed). v2.
- **No themes / plugin system in v1.** Single fixed light theme (shadcn zinc). Dark mode is a v2 toggle.
- **No native systemd mode for the dashboard server itself.** `llm dashboard serve` runs background or foreground only.
- **No advanced settings UI for per-runtime options.** Still YAML-only in v1.

## 4. V1 scope

Pages in v1:

| # | Page | Source(s) | Key actions |
|---|---|---|---|
| 1 | Overview | aggregate | health summary, running instance, recent jobs, version, quick actions |
| 2 | Runtimes | `runtimes/*/manifest.yaml`, `.installed` markers | list, install, rebuild, uninstall, view manifest |
| 3 | Models | `$LLM_MODELS/registry.json`, `du` | list, pull from HF, add local, uninstall, disk usage |
| 4 | Configs | `configs/*.yaml`, `runtimes/<id>/params.yaml`, advisor | list, create via React param grid, edit, validate, delete |
| 5 | Instance | `state/running.json`, runtime healthcheck, runtime `/metrics` | start any config, stop, switch, live logs, live metrics |
| 6 | Doctor | `requirements.yaml`, scoped `llm doctor` outputs | scoped health checks (default / runtime / dashboard) |
| 7 | Disk | `du` over `$LLM_DATA_ROOT/*` | data-root summary, per-model sizes, cache cleanup |
| 8 | History | `state/history.jsonl` | reverse-chronological event timeline with filters |
| 9 | Settings | `~/.config/llm/config.yaml` via `KEY_REGISTRY` | view + edit settings |

Header bar: project version, "update available" badge (driven by `llm update --check`), status pill ("running: `<config-id>`" / "idle"), persistent red security banner when bound non-localhost.

### Cross-cutting features

- **Jobs tray** — collapsible drawer in the sidebar listing in-flight long-running operations (installs, pulls, builds) with progress, elapsed, cancel button. Each job links to its detail sheet with full SSE-streamed log.
- **Security banner** — sticky red bar above the header whenever the server was started with `--insecure`. Non-dismissable.
- **Toast notifications** — sonner; success / error / info with optional action buttons; SSE-driven (jobs in another tab still toast on completion).

## 5. Distribution, install lifecycle, doctor, setup integration

### 5.1 New CLI commands

```text
llm dashboard install [--reset] [--skip-frontend] [--skip-python]
llm dashboard serve   [--port N] [--host H] [--foreground] [--no-open]
                      [--insecure --i-understand --allowed-host HOST:PORT]
llm dashboard           # alias for `serve`
llm dashboard uninstall [--purge]
llm dashboard status
llm dashboard stop
llm doctor dashboard    # new scope
```

### 5.2 `llm dashboard install` flow

1. **Python deps** — `uv pip install` (into the managed venv) `fastapi`, `uvicorn[standard]`, `sse-starlette`, `httpx` (already a CLI dep), `prometheus-client`. Same set declared in `pyproject.toml` as a `[dashboard]` optional-deps group so editable installs match. `--skip-python` skips.
2. **Toolchain check** — verify `node >= 20` and `npm`. On missing, print per-platform install hint (WSL: `nvm install --lts`; macOS: `brew install node`) and exit 78. Recorded as `requirements.yaml` entries under `scope: dashboard`.
3. **Frontend build** — `cd dashboard/ && npm ci && npm run build` → emits `dashboard/dist/`. `--skip-frontend` skips (useful for dev mode). `--reset` wipes `dashboard/node_modules` first then `npm ci`.
4. **Write `.installed`** — `dashboard/.installed` YAML: `installed_at`, `cli_version`, `node_version`, `npm_version`, `dist_hash` (sha256 of `dist/index.html` + `dist/assets/*` concatenated).

### 5.3 `llm dashboard serve` gating

- Refuses to start if `dashboard/.installed` is missing → suggests `llm dashboard install`.
- Refuses if `.installed.cli_version` differs from running CLI version → suggests `llm dashboard install --reset`.
- Refuses if `dist_hash` doesn't match what's on disk → suggests rebuild.
- Honors `--insecure` only with `--i-understand`; otherwise refuses with the warning quoted in §10.

### 5.4 Setup chain integration

`llm setup` gains a new optional step **after** the existing runtime / model / config / serve chain:

```text
? Install the web dashboard now? [y/N]
```

Default **No**. On yes, calls into `llm dashboard install` inline (no subprocess), surfacing the same progress.

### 5.5 `llm update` interaction

- If `dashboard/.installed` exists and the new CLI version differs from recorded:
  - Auto-runs `llm dashboard install` as part of update.
  - Skipped silently if `npm` is no longer available (next `llm dashboard serve` will refuse and tell the user).
- If `--restart` was passed and the dashboard was running, restart it after rebuild.

### 5.6 `llm doctor dashboard` checks

| Check | Severity |
|---|---|
| `node >= 20` installed | error if `.installed` present, info otherwise |
| `npm` installed | same |
| `dashboard/.installed` exists | info — "dashboard not installed" otherwise |
| `.installed.cli_version` matches current CLI version | error if mismatch |
| `dashboard/dist/index.html` exists | error if missing |
| `dist_hash` matches recorded | warning if mismatch |
| FastAPI / Uvicorn / sse-starlette / httpx / prometheus-client importable | error if any missing |
| `state/dashboard/server.pid` is alive | info — prints pid + uptime if alive |
| `--insecure` recorded in last `server.log` startup | warning, high |

### 5.7 Gitignore additions

- `dashboard/node_modules/`
- `dashboard/dist/`
- `dashboard/.installed`
- `state/metrics/`
- `state/jobs/`
- `state/dashboard/`

Committed: `dashboard/package.json`, `dashboard/package-lock.json`, `dashboard/src/**`, `dashboard/index.html`, `dashboard/vite.config.ts`, `dashboard/tailwind.config.ts`, `dashboard/tsconfig.json`, `dashboard/README.md`.

## 6. Repo & filesystem layout

### 6.1 Source tree additions

```text
local-llm-scaffold/
├── src/llm_cli/
│   ├── commands/
│   │   └── dashboard_cmd.py             # install / serve / uninstall / status / stop
│   ├── core/
│   │   ├── dashboard.py                 # build/install logic, .installed lifecycle, dist_hash
│   │   ├── disk.py                      # du wrappers for the Disk page
│   │   ├── jobs.py                      # shared job registry
│   │   └── metrics.py                   # /metrics scrape + snapshot writer + aggregator
│   └── webapi/                          # FastAPI app, importable as a module
│       ├── __init__.py
│       ├── app.py                       # create_app() factory
│       ├── deps.py                      # FastAPI dependency injectables
│       ├── errors.py                    # ErrorCode enum, response shape, exception handlers
│       ├── middleware.py                # Host header, CORS, security headers, request-id
│       ├── streams.py                   # SSE EventHub helpers
│       ├── export_openapi.py            # `python -m llm_cli.webapi.export_openapi`
│       ├── routes/
│       │   ├── health.py
│       │   ├── version.py
│       │   ├── overview.py
│       │   ├── runtimes.py
│       │   ├── models.py
│       │   ├── configs.py
│       │   ├── instance.py
│       │   ├── jobs.py
│       │   ├── doctor.py
│       │   ├── settings.py
│       │   ├── disk.py
│       │   └── history.py
│       └── static.py                    # serves dashboard/dist/ with SPA fallback
│
└── dashboard/                           # React app, separate npm package
    ├── package.json
    ├── package-lock.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── tsconfig.json
    ├── index.html
    ├── README.md
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── api/                         # generated TS client + thin wrappers
    │   ├── components/                  # shared UI primitives + shadcn-installed
    │   ├── features/                    # per-page feature folders
    │   ├── hooks/                       # useSSE, useJob, useStatus, etc.
    │   ├── lib/                         # utilities, formatting
    │   └── styles/
    ├── dist/                            # built output, gitignored, served by FastAPI
    ├── node_modules/                    # gitignored
    └── .installed                       # gitignored marker
```

### 6.2 Runtime data file additions

```text
state/
├── running.json                         # (existing)
├── history.jsonl                        # (existing)
├── logs/                                # (existing) per-config server logs
│
├── metrics/                             # NEW — per-config /metrics snapshots
│   └── <config-id>.jsonl                # one JSON object per snapshot, append-only
│
├── jobs/                                # NEW — per-job log files
│   └── <job-id>.log
│
└── dashboard/                           # NEW — dashboard-internal runtime state
    ├── server.pid                       # written by `llm dashboard serve`
    └── server.log                       # uvicorn's stdout/stderr in detached mode
```

### 6.3 Settings additions

No required additions to `KEY_REGISTRY` for v1. Optional future keys (deferred):

- `dashboard.port` (default 7878)
- `dashboard.auto_open` (default `true`)

v1 uses CLI flags only.

### 6.4 Runtime manifest extension

Each runtime manifest gains an optional `metrics:` block (see §9 for full schema). Stub-runtime gets `metrics: null`. vLLM and llamacpp get populated entries.

## 7. Backend architecture

### 7.1 App factory & lifecycle

`create_app()` in `webapi/app.py`:

1. Load settings; abort if `data_root` unwritable.
2. Initialize the job registry (`core/jobs.py`) — empty in-memory dict; create `state/jobs/` if missing.
3. Wire the in-process lifecycle event bus; subscribe the metrics scrape task.
4. On startup, read `state/running.json`; if something is running with a `metrics` manifest entry, start its scrape task.
5. Mount routers under `/api/*`, then SPA fallback at `/`.

On shutdown: cancel metrics tasks, SIGTERM all in-flight job subprocesses, flush log files, remove `state/dashboard/server.pid`.

### 7.2 Process model for `llm dashboard serve`

- **Default (background):** spawns `uvicorn llm_cli.webapi.app:create_app --factory --host 127.0.0.1 --port 7878` detached via existing `core/serve_spawn.py` plumbing; writes `state/dashboard/server.pid` and `state/dashboard/server.log`; polls `GET /api/health` until 200 OK (timeout 30s); opens browser; returns.
- **`--foreground`:** attaches uvicorn to the current terminal. Tees logs to terminal + `server.log`. SIGINT cleans up `server.pid`.
- `llm dashboard status` reads `server.pid`, `kill -0`s it, prints state + port + uptime.
- `llm dashboard stop` SIGTERMs the PID, waits up to 10s, escalates to SIGKILL.

### 7.3 "Every write goes through core" contract

Hard rule:

- FastAPI route handlers **never** touch YAML files, `state/*.json`, or subprocess `llm` invocations directly.
- They call `llm_cli.core.*` functions that the CLI's command handlers also call.
- Concretely: `POST /api/configs` → `core/registry.write_config(...)`; `POST /api/runtimes/<id>/install` → enqueues a job that calls `core/install_record.install_runtime(...)`.

Implication: every dashboard feature ships with a CLI-callable code path. Where a route needs functionality that lives only in `commands/*`, the implementation step is to extract that logic into `core/*` first (small refactor, no behavior change). Validation, atomic writes, and existing lockfile-style protections happen once, in `core/*`.

Enforcement in v1 is by code review + tests (no greppable pre-commit hook).

### 7.4 Route surface

| Method | Path | Backing core function | Notes |
|---|---|---|---|
| GET | `/api/health` | none | `{ok: true, version}`; liveness |
| GET | `/api/version` | `core/versions.current()` | CLI + dashboard recorded versions |
| GET | `/api/overview` | aggregate | landing-page payload |
| GET | `/api/runtimes` | `core/registry.list_runtimes()` | manifests + `.installed` status |
| GET | `/api/runtimes/{id}` | `core/registry.get_runtime(id)` | manifest, install record, drift |
| POST | `/api/runtimes/{id}/install` | `core/install_record.install_runtime` | returns `{job_id}` |
| POST | `/api/runtimes/{id}/rebuild` | same, `reset` arg | returns `{job_id}` |
| DELETE | `/api/runtimes/{id}` | `core/install_record.uninstall_runtime` | sync |
| GET | `/api/models` | `core/model_registry.list_models()` | reads `$LLM_MODELS/registry.json` |
| POST | `/api/models/pull` | `core/hf_client.pull(...)` | returns `{job_id}` |
| POST | `/api/models/add` | `core/model_registry.add_local(...)` | sync |
| DELETE | `/api/models/{id}` | `core/model_registry.uninstall(...)` | `?purge=true` for files |
| GET | `/api/configs` | `core/registry.list_configs()` | |
| GET | `/api/configs/{id}` | `core/registry.get_config(id)` | with `${data_root}` expansion |
| POST | `/api/configs` | `core/registry.write_config(...)` | server validates |
| PUT | `/api/configs/{id}` | same | |
| DELETE | `/api/configs/{id}` | `core/registry.delete_config(id)` | refuses if currently running |
| GET | `/api/configs/{id}/params` | `core/param_grid_models.load_for(id)` | feeds React param grid |
| GET | `/api/runtimes/{id}/default-params` | `core/param_grid_models.load_defaults(id)` | for new-config wizard |
| GET | `/api/recommendations` | `core/recommendations.compute(...)` | advisor hints |
| GET | `/api/configs/{id}/metrics/aggregate` | `core/metrics.aggregate(id, window)` | uptime, avg/P50/P95 TPS+TTFT |
| GET | `/api/configs/{id}/metrics/sparkline` | `core/metrics.sparkline(id, bucket, window)` | downsampled series |
| POST | `/api/instance/start` | `core/lifecycle.serve(...)` | `{config_id, mode}` → returns `{job_id}` for readiness wait |
| POST | `/api/instance/stop` | `core/lifecycle.stop()` | sync |
| POST | `/api/instance/switch` | `core/lifecycle.switch(...)` | `{config_id}` |
| GET | `/api/instance` | `core/lifecycle_status.current()` | reads `state/running.json` |
| GET | `/api/instance/stream` | SSE | pushes state on change + every 5s |
| GET | `/api/instance/logs/stream` | SSE | tails `state/logs/<current>.log` (or journalctl in systemd mode) |
| GET | `/api/instance/metrics/stream` | SSE | pushes latest `state/metrics/<current>.jsonl` snapshot every 5s |
| GET | `/api/jobs` | `core/jobs.list()` | all known jobs |
| GET | `/api/jobs/{id}` | `core/jobs.get(id)` | full record |
| GET | `/api/jobs/{id}/stream` | SSE | log lines + status changes |
| POST | `/api/jobs/{id}/cancel` | `core/jobs.cancel(id)` | SIGTERM → SIGKILL escalation |
| GET | `/api/doctor` | `core/doctor.run_all_scopes()` | structured per-scope results |
| GET | `/api/settings` | `core/settings.load()` + resolved | both stored + effective |
| PUT | `/api/settings/{key}` | `core/settings.set(...)` | validates against KEY_REGISTRY |
| GET | `/api/disk` | `core/disk.scan()` | per-model `du`, total, cache |
| GET | `/api/history` | `core/lifecycle.read_history(...)` | paginated, filterable |
| GET | `/api/history/stream` | SSE | new entries from `history.jsonl` |

### 7.5 SSE infrastructure

`webapi/streams.py` wraps `sse-starlette`:

- One module-level `EventHub` per topic (`instance`, `history`, per `job_id`, per running `config_id` for logs/metrics).
- Publishers (`core/lifecycle.py`, `core/jobs.py`, `core/metrics.py`) call `hub.publish(event)`; subscribers (route handlers) async-iterate `hub.subscribe()`.
- File-tail streams (logs, metrics JSONL) use polling tail with 250ms interval.
- Heartbeat comment every 15s to defeat proxy idle-timeouts.

### 7.6 Jobs module

`core/jobs.py`:

```python
@dataclass
class Job:
    id: str                              # uuid4
    kind: Literal["runtime_install", "model_pull", "dashboard_install",
                  "update", "instance_start_wait"]
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    pid: int | None
    progress: JobProgress | None         # {"percent": 0-100 | null, "stage": str}
    error: dict | None                   # {"code", "message", "details"}
```

API: `start_job(kind, callable, kwargs)`, `cancel_job(id)`, `get(id)`, `list()`.

- Surviving HTTP request lifetime, dying with the dashboard server.
- Cancellation: SIGTERM, escalate SIGKILL after 10s.
- Log file at `state/jobs/<id>.log` (stdout + stderr, append-only).
- Per-job SSE hub for live progress + status changes.

### 7.7 Middleware stack (in order)

1. **`HostHeaderMiddleware`** — Host allow-list check (see §10). 421 Misdirected Request otherwise. Runs on every request including SSE.
2. **`CORSMiddleware`** (FastAPI built-in) — allow-list per §10.
3. **`SecurityHeadersMiddleware`** — `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy: ()`, `Content-Security-Policy` per §10.
4. **Request-ID middleware** — UUID4 per request, logged with each request, returned as `X-Request-ID`.

## 8. Frontend architecture

### 8.1 Stack

- **React 19** + **TypeScript** + **Vite**.
- **Tailwind CSS v4** + **shadcn/ui** components (zinc palette, single fixed light theme in v1).
- **TanStack Router** (type-safe routes).
- **TanStack Query** for server state (every REST endpoint).
- **Zustand** (one small store) for cross-page client state.
- **React Hook Form** + **Zod** for forms.
- **sonner** for toasts.
- **OpenAPI codegen** — `openapi-typescript` (or `openapi-fetch`) generates `dashboard/src/api/generated.ts` from FastAPI's exported OpenAPI schema. Committed; regenerated via `scripts/regen-api-client.sh` (also exposed as `npm run regen-client` from `dashboard/`). CI enforces sync via `scripts/regen-api-client.sh --check`.

### 8.2 Shell layout

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Header: logo | "running: <config-id>" pill | update badge | settings│
├──────────────┬──────────────────────────────────────────────────────┤
│ Nav sidebar  │  Active page                                          │
│              │                                                       │
│ • Overview   │                                                       │
│ • Runtimes   │                                                       │
│ • Models     │                                                       │
│ • Configs    │                                                       │
│ • Instance   │                                                       │
│ • Doctor     │                                                       │
│ • Disk       │                                                       │
│ • History    │                                                       │
│ • Settings   │                                                       │
│              │                                                       │
│ Jobs tray ▴  │                                                       │
└──────────────┴──────────────────────────────────────────────────────┘
```

Security banner sits above the header bar when bound non-localhost (red, sticky, non-dismissable).

### 8.3 Routing

`/overview`, `/runtimes`, `/runtimes/:id`, `/models`, `/models/:id`, `/configs`, `/configs/new`, `/configs/:id`, `/instance`, `/jobs/:id` (modal sheet route), `/doctor`, `/doctor/runtime/:id`, `/doctor/dashboard`, `/disk`, `/history`, `/settings`.

Hard-refresh on any route returns the SPA `index.html` (FastAPI fallback).

### 8.4 State management

- **TanStack Query** for all server state. Cache invalidation on mutation success.
- **Zustand** (~100 LoC): jobs tray open/closed, sidebar collapsed, current SSE subscriptions registry, toast queue.
- No Redux, no Context-as-state-manager.

### 8.5 Real-time data via SSE

Custom `useSSE<T>(url, options)` hook wrapping `EventSource`:

- Auto-reconnect with exponential backoff (1s → 30s).
- Last event cached so a remount doesn't lose state.
- Integration with TanStack Query: SSE pushes call `queryClient.setQueryData(...)` to keep cached state in sync.

### 8.6 Forms

- **React Hook Form + Zod** for everything beyond a single text input.
- Zod schemas mirror Pydantic models (manually kept in sync for v1).
- Validation runs client-side on submit and server-side always; server response is the source of truth.

### 8.7 Param grid React component

The single hardest component. Design:

- shadcn `Table` with rows from `GET /api/configs/{id}/params` (or `GET /api/runtimes/{id}/default-params` for new configs).
- Columns: `enabled` (Checkbox), `key` (text), `value` (type-aware input), `suggestion` (subtle advisor text), `locked` (lock icon if `locked: true`), `description` (tooltip).
- Sticky header with search input (client-side filter on key + description), "show enabled only" toggle, "show locked" toggle.
- Bulk actions: "Apply all suggestions", "Reset to defaults", "Disable all optional".
- Inline badge per row: "default" / "modified" / "locked".
- On save: posts the **same `ParamCell[]` shape** that `core/param_grid_models.py` produces. Same validation, same opt-in semantics. The TUI and the React grid both consume + produce this shape — single source of truth.

### 8.8 Notifications

shadcn `sonner` toaster, top-right:

- **Success** (auto-dismiss 3s): "Config saved", "Runtime install started" (link to job).
- **Error** (sticky): "Failed to save: <message>" with expandable detail.
- **Info** (5s): "vLLM install completed", "Update available — `v1.2.0`" with action button.

Toasts dispatched from SSE events (job completion shows a toast even if navigated away).

### 8.9 Per-page summaries

#### Overview

Status pill in header; **running now** card (config / mode / port / uptime / live TPS+TTFT mini-cards / live log preview); **recent jobs** list (last 5); **system at a glance** mini-cards (disk usage, doctor green/yellow/red, version + update badge); **quick actions** (start last-used config, open most-recent config, run doctor).

#### Runtimes

Table (id, kind, installed status, build date, version recorded). Row click → detail with tabs (Manifest / Install record / Drift). Per-row actions: install, rebuild, uninstall (with confirm). Running jobs show a progress strip on the row.

#### Models

Table (id, format, size, source, registered date). Per-row: info, uninstall (with `purge` toggle), open registry entry. Top: **"Pull from HuggingFace"** form (URL + format/include/exclude/id), equivalent to `llm model pull`. **"Add local model"** secondary form for `llm model add`.

#### Configs

Table grouped by runtime. Row click → detail. Top: **"New config" button → `/configs/new` wizard** (5-step: pick runtime → pick model → param grid → review → save). Detail page tabs:

- **Overview** — runtime/model link, last run, last switch, "Run this config" with mode picker (bg/systemd; foreground unavailable from web).
- **Params** — the React param grid component, read-only by default with an "Edit" toggle.
- **Validate** — runs `core/registry.validate(id)` → green/red.
- **Raw YAML** — read-only `pre`-block. (Edit-as-YAML is v2.)

#### Instance

Single page, shape depends on `state/running.json`:

- **Nothing running:** "Start a config" picker + mode radio (bg or systemd only — fg unavailable from web) + Start button.
- **Something running:** status card (config / mode / port / pid / uptime / health pill), tabs:
  - **Logs** — virtualized terminal-style view, SSE-tailed. Pause/resume, clear, copy, scroll-lock-on-scroll.
  - **Metrics** — current TPS, TTFT, P50, P95 (large numbers) + per-metric sparkline of last 60 snapshots (5min @ 5s). SSE-driven.
  - **Switch to…** — combobox of other configs + Switch button.
- Persistent **Stop** button.
- **Foreground-mode instances** (started from CLI) appear read-only with banner "Started in foreground from terminal — use Ctrl-C in that terminal to stop."

#### Doctor

Three scopes as tabs (default / runtime / dashboard). Each check row: name, status pill, description, fix-it expandable. "Re-run" button at top. Auto-refresh on mount; no polling.

#### Disk

**Data root summary** (total, available, % full bar), **Models** (table: id, format, files, size, last accessed; per-row uninstall), **Cache** (HF cache, build cache; per-row clear with confirm). Refresh button (`du` is non-instant — spinner shown).

#### History

Virtualized list, reverse-chronological, server-paginated (25/page). Filters: action, config id, date range. Live updates via SSE.

#### Settings

Form rendered from `KEY_REGISTRY` (one input per key, type-aware via `kind`). "Save" → `PUT /api/settings/{key}` per changed field. "Reset to default" per key. Read-only display of resolved (effective) values alongside stored.

## 9. Live metrics pipeline

### 9.1 Runtime manifest extension

```yaml
metrics:
  endpoint: /metrics              # path relative to the runtime's bind host:port
  format: prometheus              # only "prometheus" supported in v1
  fields:
    tps_decode:
      promql_metric: vllm:tokens_per_second{phase="decode"}
      label: "Decode TPS"
      unit: "tok/s"
    tps_prompt:
      promql_metric: vllm:tokens_per_second{phase="prompt"}
      label: "Prompt TPS"
      unit: "tok/s"
    ttft_ms:
      promql_metric: vllm:time_to_first_token_seconds
      multiplier: 1000
      label: "TTFT"
      unit: "ms"
```

- `metrics: null` or absent means "no metrics for this runtime". UI shows "live metrics unavailable" instead of empty charts.
- **stub-runtime:** `metrics: null`. **vllm, llamacpp:** populated as part of v1 implementation.

### 9.2 Scrape task lifecycle

`core/metrics.py:MetricsScrapeTask`:

- One task per *currently-running* config with a `metrics` manifest block.
- Owned by the FastAPI app (dashboard scrapes; CLI does not).
- Started on dashboard boot if `state/running.json` shows something running with metrics declared.
- Started when `core/lifecycle.py` publishes `state_change(started, config_id)`.
- Stopped on `state_change(stopped)` or after N consecutive scrape errors.
- One scrape every **5 seconds** (fixed in v1, configurable in v2).
- httpx GET to `http://127.0.0.1:<port><endpoint>`, 2s timeout. Parse with `prometheus-client`'s `text_string_to_metric_families`. Resolve manifest's `fields` map.
- Appends one JSONL line per snapshot:

```json
{ "ts": "2026-05-20T07:30:05Z", "tps_decode": 42.3, "tps_prompt": 1234.0, "ttft_ms": 87.5 }
```

- Publishes the same snapshot to the per-config SSE hub.

### 9.3 Failure modes

| Symptom | Behavior |
|---|---|
| HTTP 4xx/5xx | Log warning, append `{"ts": "...", "error": "http_<code>"}`. Three in a row → suspend task for 60s. |
| Timeout | Append `{"ts": "...", "error": "timeout"}`. Same suspension policy. |
| Parse error | Append `{"ts": "...", "error": "parse"}`. Don't suspend (keep trying). |
| Manifest declares missing field | Field becomes `null` in snapshot. UI shows `—`. |
| Runtime restarted (PID changed) | Lifecycle SSE re-announces; task restarts cleanly. |
| Dashboard restart while serving | On startup, re-init task from `state/running.json`. Existing JSONL preserved (append-only). |

### 9.4 Aggregation

`core/metrics.py:aggregate(config_id, window="7d")` reads JSONL, filters to the window, computes:

- `samples`: count
- `avg_tps_decode`, `avg_tps_prompt`, `avg_ttft_ms`
- `p50_*`, `p95_*` (sorted-percentile, no extra deps)
- `total_uptime_seconds` from `history.jsonl` (sum of start→stop intervals)

Pure Python, no numpy/pandas. Fine up to ~1M snapshots per config (≈60 days @ 5s).

For sparklines: `GET /api/configs/{id}/metrics/sparkline?bucket=5m&window=24h` → server downsamples to one point per bucket (mean).

### 9.5 Retention

- Append-only in v1. No rotation, no truncation.
- ~120 bytes per snapshot × 5s cadence = ~2 MB/day per running config.
- v2 adds daily rollup (1-minute buckets) + opt-in pruning.

### 9.6 UI behavior matrix

| State | Page | Render |
|---|---|---|
| Running, metrics declared, samples coming in | Instance / Metrics | Big number cards (live) + 60-snapshot sparklines |
| Running, metrics declared, scrape suspended | Instance / Metrics | "Metrics scrape suspended after errors; last snapshot N seconds ago" + last numbers |
| Running, `metrics: null` | Instance / Metrics | "This runtime does not expose live metrics." Stats from history only. |
| Not running, has historical JSONL | Configs / detail | Aggregated cards (avg / P50 / P95) computed from history. Sparkline of last 24h bucketed. |
| Never run | Configs / detail | "No metrics yet — run this config to collect data." |

## 10. Security model

### 10.1 Defense layers (all on by default)

| Layer | Mechanism | Stops |
|---|---|---|
| 1. Bind | `127.0.0.1` default | Other devices on the network |
| 2. Host header | Strict allow-list middleware | DNS rebinding |
| 3. CORS | Allow-list to localhost origins | Cross-origin XHR from random pages |
| 4. CSP | Restrictive default-src `'self'` | Injected `<script>` from compromised content |
| 5. Exposure friction | `--insecure` + `--i-understand` + persistent banner | Accidental exposure |
| 6. Doctor surfacing | `llm doctor dashboard` flags exposure | Forgetting `--insecure` is on |
| 7. Documentation | `docs/DASHBOARD-SECURITY.md` | "I didn't know" |

### 10.2 Host header allow-list

```text
allowed_hosts = ["127.0.0.1:<port>", "localhost:<port>"]
if --insecure:
    allowed_hosts += hosts from --allowed-host flag
    # If none provided, fall back to <bind-host>:<port>

if request.headers["host"] not in allowed_hosts:
    return 421 Misdirected Request
```

Runs on every request (REST, SSE, static). 421 (semantically "wrong target") rather than 403.

### 10.3 CORS allow-list

```text
- http://127.0.0.1:<port>
- http://localhost:<port>
- http://127.0.0.1:5173        # Vite dev server
- http://localhost:5173
```

With `--insecure --allowed-host`, those hosts are added. **Wildcards never permitted.** HTTP only in v1; no TLS.

### 10.4 `--insecure` UX

`llm dashboard serve --insecure` alone refuses with the multi-line warning quoted below, exit code 78:

```text
═══════════════════════════════════════════════════════════════════════
  REFUSING TO START: --insecure exposes the dashboard on the network.
═══════════════════════════════════════════════════════════════════════

What --insecure means:
  • Anyone reachable on this interface can manage your LocalLLM install.
  • That includes pulling arbitrary models, starting runtimes, viewing
    your config files, and reading runtime stdout/stderr (which may
    contain prompts).
  • There is no authentication. There is no audit log.
  • This is unsafe on shared networks (coffee shops, conferences, dorms).
  • This is unsafe on cloud VMs without firewall rules.

If you actually need remote access, prefer:
  • SSH port-forward:    ssh -L 7878:127.0.0.1:7878 user@host
  • Tailscale + bind to the tailnet IP only
  • A reverse proxy with TLS and auth in front (out of scope for v1)

If you understand and accept the risk, re-run with --i-understand:
  llm dashboard serve --insecure --i-understand --allowed-host <host:port>

See: docs/DASHBOARD-SECURITY.md
```

With `--i-understand`, the warning still prints (every time), uvicorn starts, server log records `[SECURITY] Started with --insecure on <host>:<port>; allowed_hosts=<list>`.

### 10.5 In-app banner

When started with `--insecure`, every API response carries header `X-LocalLLM-Insecure: true`. The SPA renders a fixed red banner above the header bar:

```text
⚠ EXPOSED ON NETWORK
This dashboard is reachable from other devices on this network.
Anyone with the URL can manage your LocalLLM install.
[Why this is risky] [How to lock down]
```

Non-dismissable. Links open `/docs/dashboard-security#why` and `#lockdown` (served by FastAPI from markdown).

### 10.6 Content-Security-Policy

```text
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data:;
font-src 'self' data:;
connect-src 'self';
frame-ancestors 'none';
form-action 'self';
base-uri 'self';
```

- No inline `<script>`. (Vite production emits only external `<script src>`.)
- `'unsafe-inline'` for styles is Tailwind/shadcn-required and low-impact.
- `connect-src 'self'` defeats data exfiltration via XHR if XSS lands.
- `frame-ancestors 'none'` defeats clickjacking.

### 10.7 `docs/DASHBOARD-SECURITY.md` outline

1. Threat model — defended-against vs not.
2. Why localhost-only is the default.
3. The four risks of `--insecure`.
4. Safer alternatives (SSH forward, Tailscale, reverse proxy).
5. DNS rebinding — what it is, why Host header check matters.
6. Self-audit checklist (run `llm doctor dashboard`, check `server.log`, verify `--insecure` not baked into any systemd unit).

## 11. Testing & dev workflow

### 11.1 Backend (pytest)

- New directory `tests/webapi/`. New marker `webapi` in `pyproject.toml`.
- Unit tests for `core/jobs.py`, `core/metrics.py`, `core/dashboard.py`, `core/disk.py`, `webapi/middleware.py`, each route file.
- Integration tests via FastAPI `TestClient` + `httpx.AsyncClient` (for streaming). Use existing `tmp_path` + `LLM_DATA_ROOT` env-isolation fixtures.
- SSE tests via `async with httpx_client.stream(...)`: assert event ordering, assert reconnection after forced disconnect.
- Host header tests parametrized over allowed / rebinding / wildcarded hosts.
- Job lifecycle tests: start, cancel mid-flight (assert SIGTERM/SIGKILL escalation timing), start + fail (assert error captured), restart server (assert in-memory jobs are gone, log files survive).
- Metrics scrape tests: mock httpx returning prometheus text (assert JSONL append shape); mock 5xx in a row (assert suspension); mock missing field (assert null without crash).

### 11.2 Frontend (Vitest + Testing Library + msw)

- Unit tests for components with logic (param grid, useSSE hook, jobs tray store).
- Integration (route-level) with msw intercepting `/api/*`. Render a page route, assert what's on screen, simulate mutation, assert optimistic + post-success states.
- Type safety: `tsc --noEmit` in CI.
- OpenAPI contract: `scripts/regen-api-client.sh --check` in CI; drift fails.

### 11.3 End-to-end

No Playwright in v1. Integration tests cover ~80% of value; E2E is v2 once UI stabilizes.

### 11.4 CI changes

- Existing GH Actions job stays as-is for `tests/`.
- New job `dashboard-tests` runs when `dashboard/**`, `src/llm_cli/webapi/**`, or `src/llm_cli/core/{jobs,metrics,dashboard,disk}.py` change:
  - Set up Node 20 + uv.
  - `uv pip install -e ".[dev,dashboard]"`.
  - `pytest tests/webapi/ -m webapi`.
  - `cd dashboard && npm ci && npm run typecheck && npm run test && npm run build`.
  - Verify built `dist/` size ≤ 1.5 MB gzipped (CI fails over budget).
- New job `api-contract-check`:
  - `scripts/regen-api-client.sh --check` — exits non-zero if the committed `dashboard/src/api/generated.ts` would change.

### 11.5 Dev workflow

Two-terminal happy path:

```bash
# Terminal 1 — backend with reload
uv run uvicorn llm_cli.webapi.app:create_app --factory --reload --port 7878

# Terminal 2 — frontend with HMR
cd dashboard && npm run dev   # http://localhost:5173, proxies /api → :7878
```

- `llm dashboard serve --dev` is sugar that prints these two commands and exits (does not manage Vite itself).
- `dashboard/README.md` documents the loop, including the `regen-client` step after backend route changes.

Live API client regen via `scripts/regen-api-client.sh` (runs `export_openapi`, pipes into `openapi-typescript`, writes `dashboard/src/api/generated.ts`). Result committed. Pre-commit hook optional (opt-in); CI is the safety net.

## 12. Error handling

### 12.1 Backend error shape (uniform)

```json
{
  "error": {
    "code": "RUNTIME_NOT_INSTALLED",
    "message": "Runtime 'vllm' is not installed. Run `llm runtime install vllm` first.",
    "details": { "runtime_id": "vllm" },
    "fix_hint": "POST /api/runtimes/vllm/install"
  },
  "request_id": "01H..."
}
```

- One `ErrorCode` enum in `webapi/errors.py`. UI maps codes → friendly toast titles.
- 4xx for user error, 5xx for server error. Never raw stack traces; stacks go to `server.log` with `request_id`.
- Job failures: `Job.status = "failed"`, `Job.error = {code, message, details}`. UI surfaces via jobs tray with the same toast shape.

### 12.2 Frontend error UX

- Every mutation: `useMutation.onError` → sonner toast with `code`-mapped title + `message` body + "Show details" expander.
- Every query: error state → page renders an error card (not a toast).
- SSE disconnect: silent reconnect for first 3 retries, then top-banner "Lost connection to backend — retrying…" until reconnect.
- Backend unreachable (no `/api/health` for 10s): full-page overlay "Dashboard server is not responding. Run `llm dashboard status` to check."

### 12.3 CLI error consistency

- `llm dashboard install` failures use existing CLI error printing (rich panels). Same exit codes as the rest of the CLI.
- `llm dashboard serve` startup failures (port in use, install missing, `--insecure` refused) print clear remediation. No stack traces.

## 13. Performance budgets

| Budget | Threshold | Enforcement |
|---|---|---|
| JS bundle (gzipped) | ≤ 1.5 MB | CI |
| First contentful paint (cold, localhost) | ≤ 1.5s | manual smoke |
| API p95 latency (read endpoints, excluding `/api/disk`) | ≤ 50ms | manual smoke |
| SSE event latency (publish → received, localhost) | ≤ 300ms | integration test |
| FastAPI process RSS (sustained metrics scrape, 1 running config) | ≤ 150 MB | manual smoke |

No budget for `/api/disk` — `du` is unbounded; UI shows a spinner.

## 14. Open questions / v2 candidates

- **Playground / chat tab** — connect to the running OpenAI endpoint, stream responses. Deferred from v1.
- **Benchmark trigger + history viewer** — earns its own spec + plan.
- **Persistent job survival across dashboard restart** — `state/jobs/<id>.json` + PID reattach (or interruption + retry).
- **Historical time-series charts** — TanStack Charts (or similar) for full-resolution multi-day views.
- **Settings persistence for dashboard preferences** — `dashboard.port`, `dashboard.auto_open` in `KEY_REGISTRY`.
- **Dark mode toggle.**
- **Native systemd mode for the dashboard server** (`llm dashboard serve --systemd`).
- **Themes / plugin system** à la Hermes.
- **Token-based auth + TLS termination** for legitimate LAN/remote scenarios (paired with built-in reverse-proxy guidance).
- **Edit-as-YAML view for configs.**
- **Log parsing for runtimes without `/metrics`** (alternative to live scrape).
- **Per-config metrics scrape interval override.**
- **JSONL rotation / pruning policies.**

## 15. Appendix: data shapes

### 15.1 `state/dashboard/server.pid`

Plain text PID, one line.

### 15.2 `dashboard/.installed`

```yaml
installed_at: "2026-05-20T07:30:00Z"
cli_version: "1.1.0"
node_version: "20.11.1"
npm_version: "10.2.4"
dist_hash: "sha256:abcd1234..."
```

### 15.3 `state/jobs/<id>.log`

Plain text, append-only, stdout + stderr interleaved.

### 15.4 `state/metrics/<config-id>.jsonl`

One JSON object per line:

```json
{ "ts": "ISO8601", "<field_id>": <number or null>, ... }
{ "ts": "ISO8601", "error": "http_500" | "timeout" | "parse" }
```

### 15.5 Job record (REST shape)

```json
{
  "id": "01H...",
  "kind": "runtime_install",
  "status": "running",
  "created_at": "ISO8601",
  "started_at": "ISO8601",
  "finished_at": null,
  "pid": 12345,
  "progress": { "percent": 42, "stage": "compiling cuda kernels" },
  "error": null,
  "context": { "runtime_id": "vllm" }
}
```

### 15.6 ParamCell (shared TUI ↔ React contract)

Defined in `core/param_grid_models.py`. Both renderers consume and produce this shape; both call the same validation + persistence functions. Drift between renderers is prevented by tests that round-trip the shape through both paths.
