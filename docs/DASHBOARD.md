# Web Dashboard

The LocalLLM dashboard is an optional, locally-hosted web UI for managing your
LocalLLM installation: viewing runtimes, models, configs, the currently-running
instance, logs, doctor results, disk usage, and history. It is **opt-in** —
default `loco` installs do not include it.

## Install

```bash
loco dashboard install
```

This:
1. Installs FastAPI + Uvicorn + sse-starlette into the managed venv.
2. Checks Node.js 20+ and npm.
3. Runs `npm ci && npm run build` in `dashboard/`.
4. Writes `dashboard/.installed` with the current CLI version + dist hash.

Skip flags: `--skip-python`, `--skip-frontend`, `--reset` (wipe node_modules).

## Serve

```bash
loco dashboard serve                    # background, auto-opens browser
loco dashboard serve --foreground       # attached to terminal
loco dashboard serve --port 8000        # custom port
loco dashboard serve --no-open          # don't open browser
```

Server binds to `127.0.0.1` by default. To bind on a LAN or tailnet address,
use the full insecure flow (see [Security](#security) below).

## Status / stop / uninstall

```bash
loco dashboard status     # install state + server pid
loco dashboard stop       # SIGTERM the server, escalate to SIGKILL after 10s
loco dashboard uninstall  # remove .installed
loco dashboard uninstall --purge  # also delete dist/ and node_modules/
```

## Health checks

```bash
loco doctor dashboard
```

Checks Node/npm availability, dashboard install state, dist integrity, server
PID liveness, and whether the last startup used `--insecure`.

## Update

When you run `loco update` and the dashboard is installed, it will be rebuilt
automatically (best-effort; skipped if node/npm are unavailable). The dashboard
header also shows an **Update available** badge when a newer CLI release exists;
click it to run `loco update --restart` from the UI.

## Security

The dashboard has **no authentication** and defaults to **localhost-only**
binding. That is intentional: any process on your machine can already invoke
`loco` directly.

If you must expose the dashboard beyond loopback, you need all three flags:

```bash
loco dashboard serve --insecure --i-understand \
  --host <bind-address> \
  --allowed-host <host:port> [--allowed-host ...]
```

The UI shows a persistent red banner when the server is started this way.
`loco doctor dashboard` warns if the last `server.log` startup used
`--insecure`.

Read the full threat model, DNS rebinding defense, and safer alternatives
(SSH port-forward, Tailscale, reverse proxy) in
[`DASHBOARD-SECURITY.md`](DASHBOARD-SECURITY.md). The same doc is served at
`/docs/dashboard-security` while the dashboard is running.

For the full design, see
[`docs/superpowers/specs/2026-05-20-web-dashboard-design.md`](superpowers/specs/2026-05-20-web-dashboard-design.md).

## Local verification notes

- SPA static files are served from `dashboard/dist/` via `mount_spa()` in
  `src/llm_cli/webapi/app.py`. If `dist/` is missing, `/` returns HTTP 503 with
  `DASHBOARD_NOT_BUILT` and a fix hint to run `loco dashboard install`.
- `loco dashboard` commands require `repo_root` (from `loco setup` or
  `loco settings edit repo_root`). Use the dev loop in `dashboard/README.md` when
  iterating on the UI without a full CLI install.
