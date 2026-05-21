# Web Dashboard Hardening & Polish (Plan 5/5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the full security model (`--insecure` + `--i-understand` + `--allowed-host` UX, persistent in-app red banner, `DASHBOARD-SECURITY.md`, doctor exposure check), the update notifier (`loco update --check` badge in the header with one-click update), performance budget enforcement in CI (bundle size, type checks, optional smoke), and the last round of error-UX polish (acting on `fix_hint`, friendlier per-route error messages, full keyboard shortcuts). After this plan merges, the dashboard reaches "v1 complete" per the spec.

**Architecture:** No new core infrastructure. This plan adds CLI flags, middleware behavior (custom `--allowed-host` propagation), a couple of small React components (`SecurityBanner` is fully implemented; `UpdateBadge` is new), and one new doc. Most of the work is finishing what previous plans intentionally deferred so they could ship working slices.

**Tech Stack:** Unchanged. No new deps.

**Related spec:** `docs/superpowers/specs/2026-05-20-web-dashboard-design.md` (§10 Security model, §13 Performance budgets, parts of §5.5, §8.9 Overview update badge)

**Previous plans (must be merged first):** Plans 1, 2, 3, 4.

**No subsequent plans.** This completes the 5-plan implementation arc.

**Implementation branch:** `feat/web-dashboard-hardening` from `main` after Plan 4 merges.

---

## Background — what Plans 1–4 landed (and what they intentionally deferred to here)

- Plan 1: Host header allow-list, CORS allow-list, CSP, security headers, request-id. `loco dashboard serve --host` validated to `127.0.0.1` / `localhost` / `::1` only — non-localhost is refused with a stub message "non-localhost binding requires --insecure (planned)". `SecurityBanner.tsx` exists but always renders `null`.
- Plan 2: `ErrorCode` extended; `fix_hint` is captured in `errorToToast.ts` but no action is taken on it.
- Plan 3: param grid + wizard — no security touch.
- Plan 4: live metrics — no security touch.
- All four: `loco update` auto-rebuilds dashboard on version drift, but no in-app notifier exists. Performance budgets are documented in the spec but no CI gate enforces them.

This plan **adds**:
- Full `--insecure` UX (refusal without `--i-understand`, mandatory `--allowed-host`, persistent banner driven by response header).
- `DASHBOARD-SECURITY.md` (the doc that the refusal message and the in-app banner link to).
- Doctor check: warn when last `server.log` startup used `--insecure`.
- Update notifier UI (header badge + one-click update).
- CI bundle-size budget enforcement.
- `fix_hint` action handling in `errorToToast`.
- A few keyboard shortcuts (Cmd/Ctrl+K for command palette → out of scope, but `/` to focus the search input on relevant pages; Esc closes sheets/dialogs already comes free from shadcn).

---

## Cross-plan invariants (final)

- Security defaults stay safe-by-default: localhost, no auth, strict Host header.
- The dashboard never accepts a non-localhost host without three explicit signals: `--insecure`, `--i-understand`, and at least one `--allowed-host`.
- Update notifier never auto-applies updates without user confirmation.

---

## File map

**Create (Python):**
- `tests/unit/test_cli_dashboard_insecure.py`
- `tests/webapi/test_security_headers_insecure.py`

**Create (React):**
- `dashboard/src/components/UpdateBadge.tsx`
- `dashboard/src/features/update/UpdateDialog.tsx`
- `dashboard/src/hooks/useUpdateCheck.ts`

**Create (docs):**
- `docs/DASHBOARD-SECURITY.md`

**Modify (Python):**
- `src/llm_cli/commands/dashboard_cmd.py` — implement `--insecure`, `--i-understand`, `--allowed-host` (repeatable)
- `src/llm_cli/core/dashboard.py` — `start_server_background()` / `run_server_foreground()` accept `allowed_hosts`, write `[SECURITY]` line into `server.log` startup banner
- `src/llm_cli/core/doctor.py` — add the "last startup used --insecure" check to the `dashboard` scope (parses tail of `server.log`)
- `src/llm_cli/webapi/app.py` — add `X-LocalLLM-Insecure: true` header on every response when bound non-localhost; serve `/docs/dashboard-security` as rendered markdown
- `src/llm_cli/webapi/middleware.py` — when allowed_hosts include non-localhost entries, set the `X-LocalLLM-Insecure` flag on the app (read by a small response-header middleware)
- `src/llm_cli/commands/update_cmd.py` — `loco update --check --json` (machine-readable; existing `--check` stays human-readable)

**Modify (React):**
- `dashboard/src/components/SecurityBanner.tsx` — full implementation (replaces the Plan 1 `null` stub)
- `dashboard/src/components/Header.tsx` — render `<UpdateBadge />` to the right of the version string
- `dashboard/src/lib/errorToToast.ts` — when `fix_hint` is present (e.g., `POST /api/runtimes/{id}/install`), render a real "Fix" action in the toast that dispatches the corresponding mutation
- `dashboard/src/api/client.ts` — capture the `X-LocalLLM-Insecure` header from `/api/health` on first load; expose via a context the banner reads

**Modify (CI):**
- `.github/workflows/dashboard-tests.yml` — add a bundle-size budget step

**Modify (docs):**
- `docs/DASHBOARD.md` — replace the "Limitations" section with "Security" — link to `DASHBOARD-SECURITY.md`; remove the "later release" caveat about `--insecure`
- `docs/README.md` — add `DASHBOARD-SECURITY.md`

**Untouched:**
- No core architecture changes
- No new ErrorCode values
- No new API routes (except the rendered-markdown handler for `/docs/dashboard-security`)

---

## Task 1: `docs/DASHBOARD-SECURITY.md` first

**Files:**
- Create: `docs/DASHBOARD-SECURITY.md`

Writing the doc first means the refusal message and the in-app banner can link to it from day one.

- [ ] **Step 1: Write the doc**

```markdown
# LocalLLM Dashboard — Security

The LocalLLM dashboard binds to `127.0.0.1` by default and has no
authentication. This page explains why, what risks `--insecure` introduces,
and how to safely expose the dashboard if you actually need to.

## Threat model

**Defended against:**
- Other machines reaching the dashboard (kernel won't accept connections
  to `127.0.0.1` from other hosts).
- DNS rebinding attacks (Host header allow-list — even a malicious website
  visited in your browser cannot make your browser issue API calls that
  the dashboard accepts as legitimate).
- Cross-origin XHR from random web pages (strict CORS allow-list).
- Script injection in compromised content (CSP `default-src 'self'`,
  `frame-ancestors 'none'`).

**Not defended against:**
- Other processes on the same machine. Any local process can already
  shell out to `loco` directly; a localhost-only dashboard adds no new
  attack surface against that threat model.
- Attackers with file system access. The dashboard reads and writes the
  same files (`configs/*.yaml`, `state/*`, `~/.config/llm/config.yaml`)
  that the CLI does.
- Malware running in your browser (e.g., a malicious extension with
  permission to read all data on all sites). CSP narrows but does not
  eliminate this.

## Why localhost-only is the default

A dashboard that controls your local LLMs is a vector for:
- Pulling arbitrary models from anywhere on the internet.
- Exfiltrating your local model registry.
- Starting / stopping / hijacking runtimes.
- Reading runtime stdout/stderr (which may contain prompts).

None of that is theoretical. Localhost-only means "any process that can
ask the kernel to dial `127.0.0.1` has already proven it's running on
this machine, which is the threshold for trusting it with any of this."

## The four risks of `--insecure`

1. **No authentication.** Anyone on the bound interface can perform
   every action the dashboard exposes.
2. **No audit log.** No record of who did what.
3. **HTTP only.** Credentials, prompts, and outputs traverse the wire
   in clear text.
4. **Persistent.** A `--insecure` flag set in your shell history or
   tmux pane will be reused unintentionally.

`--insecure` requires `--i-understand` and at least one `--allowed-host`
specifically so that none of these can happen by accident.

## Safer alternatives

If you actually need remote access, prefer:

- **SSH port-forward.** No flags, no exposure.

  ```bash
  ssh -L 7878:127.0.0.1:7878 user@host
  ```

  Now `http://127.0.0.1:7878/` on your local machine talks to the
  dashboard on `host` over an encrypted, authenticated tunnel.

- **Tailscale or equivalent overlay network.** Bind to the tailnet IP
  only; access is restricted to your authenticated devices.

  ```bash
  # On `host`:
  loco dashboard serve --insecure --i-understand \
    --host 100.x.y.z \
    --allowed-host 100.x.y.z:7878
  ```

- **A reverse proxy with TLS and auth in front.** Out of scope for the
  CLI itself; nginx / Caddy / Cloudflare Tunnel can all do this.

## DNS rebinding (why the Host header check matters)

Even with localhost-only binding, a malicious website you visit in your
browser can use **DNS rebinding** to trick your browser into making
requests to `127.0.0.1` while believing the response comes from the
malicious origin. The defense is **strict Host header validation**:
the dashboard rejects any request whose `Host` header is not in its
allow-list, even from `127.0.0.1`.

This is why `--insecure` requires `--allowed-host` — the allow-list is
the source of truth for which hosts are legitimate.

## Self-audit checklist

```bash
# 1. Verify the dashboard isn't bound non-localhost right now.
loco dashboard status
loco doctor dashboard

# 2. Verify no systemd unit or shell rc file bakes in --insecure.
grep -r 'dashboard.*insecure' ~/.bashrc ~/.zshrc ~/.config/systemd 2>/dev/null

# 3. Verify recent server.log startups didn't use --insecure.
tail -n 200 state/dashboard/server.log | grep -i security
```

If any of those show evidence of exposure, stop the server and re-evaluate.
```

- [ ] **Step 2: Commit**

```bash
git add docs/DASHBOARD-SECURITY.md
git commit -m "docs(dashboard): security threat model, --insecure risks, safer alternatives"
```

---

## Task 2: `loco dashboard serve --insecure --i-understand --allowed-host`

**Files:**
- Modify: `src/llm_cli/commands/dashboard_cmd.py`
- Modify: `src/llm_cli/core/dashboard.py`
- Create: `tests/unit/test_cli_dashboard_insecure.py`

CLI surface:

```text
loco dashboard serve --insecure --i-understand \
                    --allowed-host HOST:PORT [--allowed-host ...]
```

Behavior:
- `--insecure` alone → refuses with the multi-line warning from spec §10.4 (exit 78).
- `--insecure --i-understand` without `--allowed-host` → refuses asking for explicit host.
- All three present → starts; allowed_hosts = `{127.0.0.1:port, localhost:port, *allowed_hosts_flag}`. Logs `[SECURITY] Started with --insecure ...` line into `server.log`.

- [ ] **Step 1: Tests**

```python
def test_serve_insecure_alone_refuses(monkeypatch):
    # Don't need real install — refusal happens before verify_installed()
    result = runner.invoke(app, ["dashboard", "serve", "--insecure"])
    assert result.exit_code == 78
    assert "REFUSING TO START" in (result.stdout + (result.stderr or ""))
    assert "--i-understand" in (result.stdout + (result.stderr or ""))


def test_serve_insecure_without_allowed_host_refuses(monkeypatch):
    result = runner.invoke(app, ["dashboard", "serve", "--insecure", "--i-understand"])
    assert result.exit_code == 78
    assert "--allowed-host" in (result.stdout + (result.stderr or ""))


def test_serve_insecure_full_args_proceeds(monkeypatch, tmp_path):
    # Stub out verify_installed and start_server_background
    monkeypatch.setattr("llm_cli.core.dashboard.verify_installed",
                        lambda v: ("ok", ""))
    captured = {}
    def fake_start(host, port, allowed_hosts=None):
        captured["host"] = host
        captured["port"] = port
        captured["allowed_hosts"] = allowed_hosts
        return 1234
    monkeypatch.setattr("llm_cli.core.dashboard.start_server_background", fake_start)
    monkeypatch.setattr("llm_cli.core.dashboard.open_browser", lambda *a, **k: None)

    result = runner.invoke(app, [
        "dashboard", "serve",
        "--insecure", "--i-understand",
        "--host", "0.0.0.0",
        "--allowed-host", "192.168.1.50:7878",
        "--no-open",
    ])
    assert result.exit_code == 0, (result.stdout + (result.stderr or ""))
    assert "192.168.1.50:7878" in captured["allowed_hosts"]
```

- [ ] **Step 2: Implement**

```python
_LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}

_INSECURE_REFUSAL = """\

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
  loco dashboard serve --insecure --i-understand --allowed-host <host:port>

See: docs/DASHBOARD-SECURITY.md
"""


@app.command()
def serve(
    port: Annotated[int, typer.Option("--port")] = 7878,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    foreground: Annotated[bool, typer.Option("--foreground")] = False,
    no_open: Annotated[bool, typer.Option("--no-open")] = False,
    insecure: Annotated[bool, typer.Option("--insecure")] = False,
    i_understand: Annotated[bool, typer.Option("--i-understand")] = False,
    allowed_host: Annotated[list[str], typer.Option("--allowed-host")] = [],
) -> None:
    if insecure and not i_understand:
        typer.secho(_INSECURE_REFUSAL, fg=typer.colors.RED, err=True)
        raise typer.Exit(code=78)

    if insecure and i_understand and not allowed_host:
        typer.secho(
            "Refusing to start: --insecure --i-understand requires at least one "
            "--allowed-host HOST:PORT (DNS rebinding defense). See docs/DASHBOARD-SECURITY.md.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=78)

    if not insecure and host not in _LOCALHOST_HOSTS:
        typer.secho(
            f"Refusing to bind to {host}. Non-localhost binding requires "
            "--insecure --i-understand --allowed-host HOST:PORT.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=78)

    if insecure and i_understand:
        # Re-print the warning every time, so the user always sees it.
        typer.secho(_INSECURE_REFUSAL.rstrip(), fg=typer.colors.YELLOW, err=True)
        typer.echo("")

    verdict, reason = dash.verify_installed(current_cli_version())
    if verdict != "ok":
        typer.secho(
            f"Dashboard is not ready ({verdict}): {reason}. "
            "Run `loco dashboard install`"
            + (" --reset" if verdict in ("version_mismatch", "hash_mismatch") else "")
            + ".",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=78)

    allowed_hosts: set[str] = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if insecure:
        allowed_hosts.update(allowed_host)

    if foreground:
        typer.echo(f"Starting dashboard on http://{host}:{port}/ (foreground)")
        if not no_open:
            dash.open_browser(host, port)
        dash.run_server_foreground(host, port, allowed_hosts=allowed_hosts, insecure=insecure)
        return

    try:
        pid = dash.start_server_background(host, port, allowed_hosts=allowed_hosts, insecure=insecure)
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.secho(f"Dashboard started on http://{host}:{port}/ (pid {pid})", fg=typer.colors.GREEN)
    if not no_open:
        dash.open_browser(host, port)
```

Update `core/dashboard.py` server-start helpers to accept `allowed_hosts: set[str]` and `insecure: bool`. Propagate via env:

```python
def start_server_background(host: str, port: int, *, allowed_hosts: set[str] | None = None, insecure: bool = False) -> int:
    allowed_hosts = allowed_hosts or {f"127.0.0.1:{port}", f"localhost:{port}"}
    env = os.environ.copy()
    env["LLM_DASHBOARD_ALLOWED_HOSTS"] = ",".join(sorted(allowed_hosts))
    if insecure:
        env["LLM_DASHBOARD_INSECURE"] = "1"
    log_path = server_log_path()
    with log_path.open("ab") as f:
        f.write(f"[SECURITY] Started with --insecure={insecure} on {host}:{port}; "
                f"allowed_hosts={sorted(allowed_hosts)}\n".encode())
    # ... rest of existing implementation, using `env`
```

- [ ] **Step 3: Run — PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(dashboard): full --insecure UX with --i-understand and --allowed-host gates"
```

---

## Task 3: Backend — `X-LocalLLM-Insecure` response header

**Files:**
- Modify: `src/llm_cli/webapi/app.py`
- Modify: `src/llm_cli/webapi/middleware.py`
- Create: `tests/webapi/test_security_headers_insecure.py`

Add an env-driven flag to `SecurityHeadersMiddleware`: when `LLM_DASHBOARD_INSECURE=1` is set, every response carries `X-LocalLLM-Insecure: true`.

- [ ] **Step 1: Test**

```python
def test_response_carries_insecure_header_when_env_set(monkeypatch):
    monkeypatch.setenv("LLM_DASHBOARD_INSECURE", "1")
    app = create_app(allowed_hosts={"testserver", "192.168.1.50:7878"})
    client = TestClient(app)
    r = client.get("/api/health", headers={"Host": "testserver"})
    assert r.headers.get("X-LocalLLM-Insecure") == "true"


def test_response_omits_insecure_header_when_env_unset():
    app = create_app(allowed_hosts={"testserver"})
    client = TestClient(app)
    r = client.get("/api/health", headers={"Host": "testserver"})
    assert "X-LocalLLM-Insecure" not in r.headers
```

- [ ] **Step 2: Implement**

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, insecure: bool = False) -> None:
        super().__init__(app)
        self.insecure = insecure

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "()"
        response.headers["Content-Security-Policy"] = CSP
        if self.insecure:
            response.headers["X-LocalLLM-Insecure"] = "true"
        return response
```

And in `create_app()`:

```python
import os

def create_app(*, allowed_hosts: set[str] | None = None, cors_origins: list[str] | None = None) -> FastAPI:
    # ... existing setup ...
    insecure = os.environ.get("LLM_DASHBOARD_INSECURE") == "1"
    app.add_middleware(SecurityHeadersMiddleware, insecure=insecure)
    # ... rest unchanged ...
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(webapi): X-LocalLLM-Insecure response header when bound non-localhost"
```

---

## Task 4: Backend — serve `DASHBOARD-SECURITY.md` at `/docs/dashboard-security`

**Files:**
- Modify: `src/llm_cli/webapi/app.py`

Add a route that reads `docs/DASHBOARD-SECURITY.md` and returns it as HTML (use the `markdown-it-py` package if present, else just `<pre>` it for v1 — the in-app banner links to it but the content is meant to be readable, not pretty). Simplest v1: serve raw markdown with `Content-Type: text/plain; charset=utf-8` and rely on the browser's native rendering.

```python
from fastapi.responses import PlainTextResponse


@app.get("/docs/dashboard-security", include_in_schema=False)
def dashboard_security_doc():
    p = resolve_settings().repo_root / "docs" / "DASHBOARD-SECURITY.md"
    return PlainTextResponse(p.read_text(encoding="utf-8"))
```

Commit: `feat(webapi): serve DASHBOARD-SECURITY.md at /docs/dashboard-security`.

---

## Task 5: React — full `<SecurityBanner>`

**Files:**
- Modify: `dashboard/src/components/SecurityBanner.tsx`
- Modify: `dashboard/src/api/client.ts`

API client wrapper exposes the most recent `X-LocalLLM-Insecure` header via a small atom (`useExposureState`).

```ts
// dashboard/src/api/client.ts (additions)
import { atom, useAtom } from 'jotai'   // or: a one-line Zustand store; do whatever's smallest

export const insecureAtom = atom(false)

const baseFetch = createClient<paths>({
  baseUrl: '/api',
  fetch: async (input, init) => {
    const r = await fetch(input, init)
    // Update on every response — cheap, header is set unconditionally on the response.
    const val = r.headers.get('x-localllm-insecure') === 'true'
    // Use store.set(...) in actual impl; avoid React state mutation in fetch handler.
    setInsecure(val)
    return r
  },
})
```

(If introducing `jotai` is overkill, use Zustand which is already a dep.)

`SecurityBanner.tsx`:

```tsx
import { useInsecure } from '@/store'

export function SecurityBanner() {
  const insecure = useInsecure()
  if (!insecure) return null
  return (
    <div className="bg-red-600 text-white px-4 py-2 text-sm sticky top-0 z-50 flex items-center gap-3">
      <span className="text-xl">⚠</span>
      <div className="flex-1">
        <div className="font-semibold">EXPOSED ON NETWORK</div>
        <div>
          This dashboard is reachable from other devices on this network.
          Anyone with the URL can manage your LocalLLM install.
        </div>
      </div>
      <a className="underline" href="/docs/dashboard-security#risks" target="_blank">Why this is risky</a>
      <a className="underline" href="/docs/dashboard-security#lockdown" target="_blank">How to lock down</a>
    </div>
  )
}
```

(Adjust Zustand store to carry `insecure: boolean` and `setInsecure(v)`.)

- [ ] **Step 1: Test** — render with insecure=true: banner visible; with false: hidden.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): full red SecurityBanner driven by X-LocalLLM-Insecure header"
```

---

## Task 6: Doctor — flag recent `--insecure` startup

**Files:**
- Modify: `src/llm_cli/core/doctor.py`

In `_dashboard_scope_checks()`, append:

```python
def _check_insecure_in_recent_log() -> CheckResult:
    import re
    log = dash.server_log_path()
    if not log.is_file():
        return CheckResult(name="dashboard last startup not --insecure",
                           status="ok", message="No server.log present.")
    tail = log.read_text(encoding="utf-8")[-4096:]
    # find the last [SECURITY] line
    matches = re.findall(r"\[SECURITY\].*", tail)
    if not matches:
        return CheckResult(name="dashboard last startup not --insecure",
                           status="ok", message="No --insecure in recent startups.")
    last = matches[-1]
    if "--insecure=True" in last:
        return CheckResult(
            name="dashboard last startup not --insecure",
            status="warning",
            message=f"Last dashboard startup used --insecure: {last.strip()}. "
                    "If unintentional, restart without --insecure.",
        )
    return CheckResult(name="dashboard last startup not --insecure",
                       status="ok", message="Last startup was localhost-only.")

# inside _dashboard_scope_checks:
results.append(_check_insecure_in_recent_log())
```

- [ ] **Step 1: Test** — seed a `server.log` with `--insecure=True`; assert warning. Without it: assert ok.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(doctor): warn when recent dashboard startup used --insecure"
```

---

## Task 7: `loco update --check --json` machine-readable output

**Files:**
- Modify: `src/llm_cli/commands/update_cmd.py`

Existing `--check` prints human-readable text. Add `--json` to print:

```json
{"current": "1.1.0", "latest": "1.2.0", "update_available": true, "release_url": "https://..."}
```

The dashboard polls this via `subprocess.run(["llm", "update", "--check", "--json"], ...)` from a new minor backend route, OR — cleaner — a new `core/versions.py:check_for_update() -> UpdateInfo` function that the dashboard route calls directly. Pick the latter (no subprocess from the webapi).

- [ ] **Step 1: Extract update-check logic into `core/versions.py` if not already there**

```python
@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: str
    update_available: bool
    release_url: str | None


def check_for_update() -> UpdateInfo:
    # whatever the existing update --check does — refactored to return a value
    ...
```

- [ ] **Step 2: Wire CLI**

```python
@app.command()
def update(
    # existing args...
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable output (only with --check).")] = False,
) -> None:
    if check and json_output:
        info = versions.check_for_update()
        typer.echo(json.dumps(asdict(info)))
        return
    # existing flow...
```

- [ ] **Step 3: Backend route** — add `GET /api/update/check` to a new `webapi/routes/update.py` (5-min cache to avoid hammering GitHub on every page load):

```python
from datetime import UTC, datetime, timedelta
from fastapi import APIRouter
from llm_cli.core import versions

router = APIRouter(tags=["update"])

_CACHE: tuple[datetime, dict] | None = None


@router.get("/update/check")
def check_update():
    global _CACHE
    if _CACHE and datetime.now(tz=UTC) - _CACHE[0] < timedelta(minutes=5):
        return _CACHE[1]
    info = versions.check_for_update()
    body = {"current": info.current, "latest": info.latest,
            "update_available": info.update_available, "release_url": info.release_url}
    _CACHE = (datetime.now(tz=UTC), body)
    return body
```

- [ ] **Step 4: Tests + commit**

```bash
git commit -m "feat(update): --check --json + /api/update/check with 5-min cache"
```

---

## Task 8: React — `<UpdateBadge>` + `<UpdateDialog>`

**Files:**
- Create: `dashboard/src/components/UpdateBadge.tsx`
- Create: `dashboard/src/features/update/UpdateDialog.tsx`
- Create: `dashboard/src/hooks/useUpdateCheck.ts`
- Modify: `dashboard/src/components/Header.tsx`

`useUpdateCheck()`: `useQuery(['update', 'check'])` against `/api/update/check`, refetched every 6 hours.

`UpdateBadge`:
- Hidden if `!data?.update_available`.
- Renders a small `Badge` "Update available: vX.Y.Z" in the header. Click → opens `UpdateDialog`.

`UpdateDialog`:
- shadcn `Dialog`.
- Body: current version, latest version, link to release notes (`release_url`).
- "Update now" button → runs `useStartJob` against — wait, this requires a `POST /api/update` route. Add that as a sub-step:

```python
# webapi/routes/update.py
@router.post("/update")
def trigger_update(restart_dashboard: bool = True):
    from llm_cli.core import jobs as jobs_module
    argv = ["llm", "update"]
    if restart_dashboard:
        argv.append("--restart")
    job_id = jobs_module.registry().start_subprocess(
        kind="update", context={"restart_dashboard": restart_dashboard}, argv=argv,
    )
    return {"job_id": job_id}
```

- "Cancel" button → just closes.

- [ ] **Step 1: Tests** — render badge with/without update available; click → dialog opens; click "Update now" → mutation fires.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): UpdateBadge + UpdateDialog with one-click `loco update --restart`"
```

---

## Task 9: `fix_hint` action in `errorToToast`

**Files:**
- Modify: `dashboard/src/lib/errorToToast.ts`

Plan 2 stubbed this with "TODO Plan 5". Implement it now.

```ts
import { toast } from 'sonner'
import { api } from '@/api/client'

// fix_hint can be an HTTP verb + path (e.g. "POST /api/runtimes/vllm/install"),
// which the toast knows how to dispatch.
const HINT_RE = /^(GET|POST|PUT|DELETE)\s+(\/api\/.+)$/

function parseFixHint(hint: string | null | undefined) {
  if (!hint) return null
  const m = HINT_RE.exec(hint)
  if (!m) return null
  return { method: m[1] as 'GET'|'POST'|'PUT'|'DELETE', path: m[2] }
}

async function executeFixHint(parsed: { method: string; path: string }) {
  // For Plan 5, only support POST hints (the common case for "install this").
  if (parsed.method !== 'POST') return
  try {
    const r = await fetch(parsed.path, { method: 'POST' })
    if (r.ok) toast.success('Fix applied')
    else toast.error('Fix failed', { description: await r.text() })
  } catch (e) {
    toast.error('Fix failed', { description: String(e) })
  }
}

export function errorToToast(err: unknown) {
  const body = (err as any)?.error
  if (body && body.code) {
    const fix = parseFixHint(body.fix_hint)
    toast.error(TITLES[body.code] ?? body.code, {
      description: body.message,
      action: fix ? { label: 'Fix', onClick: () => executeFixHint(fix) } : undefined,
    })
    return
  }
  toast.error('Request failed', { description: String(err) })
}
```

- [ ] **Step 1: Tests** — assert toast rendered with action button when `fix_hint` is a parseable POST.

- [ ] **Step 2: Implement + commit.**

```bash
git commit -m "feat(dashboard): fix_hint action in toasts dispatches POST routes"
```

---

## Task 10: CI — bundle size budget

**Files:**
- Modify: `.github/workflows/dashboard-tests.yml`
- Create: `dashboard/scripts/check-bundle-size.mjs`

`dashboard/scripts/check-bundle-size.mjs`: walks `dist/assets/*` after build, sums sizes, gzips conceptually using `zlib.gzipSync`, checks total against 1_500_000 bytes (1.5 MB gzipped per spec §13).

```js
#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'

const BUDGET = 1_500_000  // 1.5 MB gzipped

const dist = path.resolve('dashboard/dist/assets')
if (!fs.existsSync(dist)) {
  console.error('dashboard/dist/assets not found — run `npm run build` first.')
  process.exit(2)
}

let total = 0
for (const name of fs.readdirSync(dist)) {
  const p = path.join(dist, name)
  const stat = fs.statSync(p)
  if (!stat.isFile()) continue
  const raw = fs.readFileSync(p)
  const gz = zlib.gzipSync(raw, { level: 9 })
  total += gz.length
  console.log(`${name}: ${stat.size} bytes raw, ${gz.length} bytes gzip`)
}

console.log(`---\nTotal gzipped: ${total} bytes (budget ${BUDGET})`)
if (total > BUDGET) {
  console.error(`BUDGET EXCEEDED by ${total - BUDGET} bytes`)
  process.exit(1)
}
```

Workflow addition:

```yaml
      - run: node dashboard/scripts/check-bundle-size.mjs
```

Add it after `npm run build`.

- [ ] **Step 1: Commit**

```bash
git commit -m "ci(dashboard): enforce 1.5 MB gzipped bundle budget"
```

---

## Task 11: Final docs pass

**Files:**
- Modify: `docs/DASHBOARD.md`
- Modify: `docs/README.md`

`docs/DASHBOARD.md`: replace the "Limitations of this release" section with a "Security" section that links to `DASHBOARD-SECURITY.md`. Remove all "planned for a later release" caveats — they're done.

`docs/README.md`: add `DASHBOARD-SECURITY.md` to the index.

Commit: `docs(dashboard): final documentation pass — security, no more 'later release' caveats`.

---

## Task 12: End-to-end smoke + PR

- [ ] **Step 1: Localhost smoke** — start dashboard normally, verify no banner, no "update available" badge when on latest.
- [ ] **Step 2: Insecure smoke** — `loco dashboard serve --insecure` → refused. `--insecure --i-understand` → refused. `--insecure --i-understand --host 192.168.x.y --allowed-host 192.168.x.y:7878` → starts, banner red in browser, `loco doctor dashboard` warns.
- [ ] **Step 3: Update notifier smoke** — fake a higher version in `core/versions.check_for_update()` → badge appears → click → dialog → "Update now" triggers a job (cancel before it actually runs git pull, this is a smoke test).
- [ ] **Step 4: Bundle size** — `node dashboard/scripts/check-bundle-size.mjs` locally → assert under budget.
- [ ] **Step 5: All tests green** — `uv run pytest -q && cd dashboard && npm run typecheck && npm run test && npm run build && scripts/regen-api-client.sh --check`.
- [ ] **Step 6: PR**

```bash
git push -u origin feat/web-dashboard-hardening
gh pr create --title "feat(dashboard): security hardening, update notifier, perf budget (Plan 5/5)" --body "..."
```

---

## Self-review

1. **Spec coverage:** §10.4 `--insecure` UX (refusal + i-understand + allowed-host) ✓; §10.5 in-app banner driven by `X-LocalLLM-Insecure` header ✓; §10.7 DASHBOARD-SECURITY.md ✓; §5.6 doctor scope's `--insecure` recent-log check ✓; §8.9 Overview update badge ✓; §13 performance budget enforced in CI ✓.
2. **Placeholder scan:** none.
3. **Type consistency:** `UpdateInfo` defined once in `core/versions.py`, surfaced through `/api/update/check` unchanged. `insecure` state propagated via env (`LLM_DASHBOARD_INSECURE=1`) + response header (`X-LocalLLM-Insecure`) consistently.
4. **Branch hygiene:** `feat/web-dashboard-hardening` from `main` after Plan 4 merges.
5. **Conventional commits:** all `feat(...)` / `ci(...)` / `docs(...)` with appropriate scopes.

**With this plan merged, the dashboard reaches v1 complete per the spec.**
