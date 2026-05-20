# Web Dashboard

The LocalLLM dashboard is an optional, locally-hosted web UI for managing your
LocalLLM installation: viewing runtimes, models, configs, the currently-running
instance, logs, doctor results, disk usage, and history. It is **opt-in** —
default `llm` installs do not include it.

## Install

```bash
llm dashboard install
```

This:
1. Installs FastAPI + Uvicorn + sse-starlette into the managed venv.
2. Checks Node.js 20+ and npm.
3. Runs `npm ci && npm run build` in `dashboard/`.
4. Writes `dashboard/.installed` with the current CLI version + dist hash.

Skip flags: `--skip-python`, `--skip-frontend`, `--reset` (wipe node_modules).

## Serve

```bash
llm dashboard serve                    # background, auto-opens browser
llm dashboard serve --foreground       # attached to terminal
llm dashboard serve --port 8000        # custom port
llm dashboard serve --no-open          # don't open browser
```

Server binds to `127.0.0.1` by default. Non-localhost binding will require a
`--insecure` flag (planned for a later release; currently refused).

## Status / stop / uninstall

```bash
llm dashboard status     # install state + server pid
llm dashboard stop       # SIGTERM the server, escalate to SIGKILL after 10s
llm dashboard uninstall  # remove .installed
llm dashboard uninstall --purge  # also delete dist/ and node_modules/
```

## Health checks

```bash
llm doctor dashboard
```

Checks Node/npm availability, dashboard install state, dist integrity, server
PID liveness.

## Update

When you run `llm update` and the dashboard is installed, it will be rebuilt
automatically (best-effort; skipped if node/npm are unavailable).

## Limitations of this release

This is the read-only release. The following arrive in subsequent releases:

- Mutations (create/edit/delete configs, install/uninstall runtimes, pull
  models, start/stop instances) — next release
- React param grid + new-config wizard
- Live metrics charts
- `--insecure` for LAN binding, with appropriate warnings

For the full design, see
[`docs/superpowers/specs/2026-05-20-web-dashboard-design.md`](superpowers/specs/2026-05-20-web-dashboard-design.md).

## Local verification notes

- SPA static files are served from `dashboard/dist/` via `mount_spa()` in
  `src/llm_cli/webapi/app.py`. If `dist/` is missing, `/` returns HTTP 503 with
  `DASHBOARD_NOT_BUILT` and a fix hint to run `llm dashboard install`.
- `llm dashboard` commands require `repo_root` (from `llm setup` or
  `llm settings edit repo_root`). Use the dev loop in `dashboard/README.md` when
  iterating on the UI without a full CLI install.
