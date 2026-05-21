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

<a id="risks"></a>

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

<a id="lockdown"></a>

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
