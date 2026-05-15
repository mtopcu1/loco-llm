# LocalLLM Scaffolding Design

_Date: 2026-05-15_
_Status: Approved by user, ready for implementation planning_

## 1. Purpose

A personal repository for documenting and storing different local-LLM runtime configurations, with the ability to benchmark them, switch between them, and pin one as a "daily driver" that serves an OpenAI-compatible endpoint.

The repo is **a control plane**, not a data store. It contains text only — manifests, configs, scripts, benchmark results — and never weights or runtime source trees. The actual heavy artifacts live in WSL2's native filesystem.

## 2. Goals

- **Reproducible configurations** — any (runtime, model, flags) combination is named, versioned, and re-runnable.
- **Easy switching** — a single CLI command stops the current server and starts another config; one config can be pinned as the daily driver.
- **Reproducible benchmarks** — every benchmark run captures versions, hashes, hardware, and the exact config used, so results are meaningful months later.
- **Forward-compatible with future UI** — CLI today, but the data model is designed so a TUI or web dashboard can be added later as a pure presentation layer.
- **Documented processes** — every workflow (adding a model, runtime, config, benchmark) has a HOWTO in `docs/` that is kept current.

## 3. Non-goals

- Not a multi-host system. Single workstation only. (Multi-host can be added later without changing the layout.)
- Not a packaging or distribution system. Other people can read the repo, but it's tuned for one user.
- Not a runtime — this repo does not implement vLLM, llama.cpp, etc. It orchestrates them.
- Not a benchmark framework — benchmarks are thin wrappers around existing tools (`vllm bench`, `llama-bench`, `lm-eval`, etc.), not a homegrown workload spec.
- Not native Windows. WSL2 is the single execution environment.

## 4. Execution environment

- **Host:** Windows 11.
- **Runtime environment:** WSL2 (Ubuntu), with `systemd=true` in `/etc/wsl.conf`.
- **Repo location:** `/mnt/c/Private/Projects/LocalLLM/` (NTFS, host filesystem — fine for text).
- **Data root:** `~/llm/` inside WSL ext4 (fast; can be moved to a dedicated VHDX or physical drive later by editing `paths.yaml`).
  - `~/llm/runtimes/` — built runtime source trees and venvs
  - `~/llm/models/` — model weights
  - `~/llm/cache/` — HuggingFace cache, build cache
- **GPU:** NVIDIA driver on the Windows host exposes the GPU into WSL via the WSL CUDA driver.

Models and runtime source trees **must not** be stored on `/mnt/c/...` or any DrvFs-mounted Windows drive; the NTFS-through-translation-layer performance is unacceptable for weight loading and builds.

## 5. Repository layout

```
LocalLLM/
├── README.md
├── paths.yaml                         # WSL data-root location (single source of truth)
├── requirements.yaml                  # external prerequisites (source of truth)
├── requirements.md                    # auto-generated from requirements.yaml
├── specs.md                           # auto-generated host/WSL/GPU profile
│
├── runtimes/
│   └── {runtime-id}/                  # e.g. vllm-cuda, llamacpp-cuda, ollama-default
│       ├── README.md
│       ├── manifest.yaml              # upstream pointer + arg schema
│       ├── build.sh                   # clones + builds into ~/llm/runtimes/{id}/
│       ├── serve.sh                   # foreground server, reads a config
│       ├── healthcheck.sh             # exits 0 when OpenAI endpoint is ready
│       └── version.sh                 # (optional) prints the actual built version
│
├── models/
│   └── {model-id}/                    # e.g. llama3-70b-q4km, qwen2-7b-fp16
│       ├── README.md
│       ├── manifest.yaml              # source pointer + sha256s
│       └── pull.sh                    # downloads into ~/llm/models/{id}/
│
├── configs/                           # flat — each file is a full launch unit
│   ├── vllm-cuda__llama3-70b-q4km__throughput.yaml
│   ├── vllm-cuda__qwen2-7b-fp16__low-latency.yaml
│   └── llamacpp-cuda__qwen2-7b-q5km__default.yaml
│
├── benchmarks/
│   └── {benchmark-id}/
│       ├── README.md
│       ├── bench.yaml                 # tiny: needs_server, description
│       ├── run.sh                     # invokes a preexisting tool, writes to $LLM_OUTPUT_DIR
│       └── results/
│           └── {config-id}/
│               └── {YYYY-MM-DDTHH-MM-SSZ}/
│                   ├── run.json       # snapshot: versions, hashes, hw, config copy
│                   ├── metrics.json   # normalized summary
│                   ├── server.log
│                   ├── client.log
│                   └── raw/           # native artifacts from the tool
│
├── state/                             # runtime state
│   ├── active.yaml                    # pinned daily-driver config-id (committed)
│   ├── running.json                   # live pids, ports, started-at (gitignored)
│   ├── history.jsonl                  # append-only event log (gitignored)
│   └── logs/                          # daily-driver serve logs (gitignored)
│
├── scripts/
│   ├── llm                            # CLI entrypoint (Python + Typer)
│   ├── _orchestrator.py               # shared serve/bench lifecycle
│   ├── _snapshot.py                   # collects run.json fields
│   ├── _specs.py                      # hardware/env detection
│   └── _doctor.py                     # requirements + sanity checks
│
└── docs/
    ├── README.md
    ├── wsl-setup.md
    ├── repo-conventions.md
    ├── add-a-runtime.md
    ├── add-a-model.md
    ├── add-a-config.md
    ├── add-a-benchmark.md
    └── runtimes/                      # per-runtime deep notes as needed
```

### 5.1 `paths.yaml`

Single source of truth for where data lives in WSL.

```yaml
data_root: ~/llm
runtimes: ${data_root}/runtimes
models:   ${data_root}/models
cache:    ${data_root}/cache
```

`llm init` reads this, expands `~`, and writes a resolved `.llm-env` that scripts source. Moving to a different drive = edit `paths.yaml` and re-init.

### 5.2 Gitignore strategy

- **Committed:** all source, manifests, configs, scripts, benchmark `results/` directories, `state/active.yaml`.
- **Gitignored:** `state/running.json`, `state/history.jsonl`, `state/logs/`, `.llm-env`, any `results/**/raw/_large/` escape-hatch directory.

Rationale: results are JSON + small CSVs + text logs. They compress well and are the most valuable historical artifact this repo produces. Committing them by default makes the repo self-documenting. The `_large/` convention lets individual benchmarks opt out for genuinely huge native artifacts.

## 6. Per-folder unit contracts

### 6.1 `runtimes/{runtime-id}/`

Every runtime fulfills the same three-script contract.

**`manifest.yaml`:**

```yaml
id: vllm-cuda
display_name: vLLM (CUDA)
upstream:
  repo: https://github.com/vllm-project/vllm
  ref: v0.7.3                  # tag, branch, or commit sha — pinned
  fork: null                   # set to your fork URL if applicable
patches: []                    # optional .patch files relative to this folder
arg_schema:                    # which serve.args this runtime exposes (for future UI form rendering)
  tensor-parallel-size: { type: int, min: 1, max: 8, default: 1 }
  max-model-len:        { type: int, min: 512, default: 8192 }
  gpu-memory-utilization: { type: float, min: 0.1, max: 1.0, default: 0.9 }
  dtype: { type: enum, values: [auto, float16, bfloat16, float32], default: auto }
notes: |
  Free-form. Build gotchas, quirks, etc.
```

`arg_schema` is optional and grows over time. Not validated against today; rendered into form UI later.

**`build.sh`** — idempotent. Clones into `$LLM_DATA_ROOT/runtimes/{id}/src`, applies patches, builds, installs into a per-runtime venv at `$LLM_DATA_ROOT/runtimes/{id}/venv`. Re-running on an already-built ref is a fast no-op.

**`serve.sh --config <path>`** — universal contract:

- Runs in the foreground; no double-fork.
- Reads the config, sources the runtime's venv, exec's the actual server.
- Prints a single line `LLM_READY port=<n> model=<id>` to stdout when the OpenAI endpoint is up. This complements (does not replace) the healthcheck poll.
- Traps SIGTERM, forwards it to the server, waits for clean exit.

**`healthcheck.sh --config <path>`** — exits 0 when the OpenAI endpoint is ready (e.g. `curl -fsS http://localhost:$PORT/v1/models`). Same arg shape as serve.sh.

**`version.sh`** _(optional)_ — prints a one-line version string used in `run.json` (e.g. `vllm 0.7.3+cu124`). If absent, the snapshot records the manifest ref.

### 6.2 `models/{model-id}/`

**`manifest.yaml`:**

```yaml
id: llama3-70b-q4km
display_name: Llama 3 70B (Q4_K_M, gguf)
source:
  kind: huggingface              # or "url", "ollama", "local"
  repo: meta-llama/Meta-Llama-3-70B-Instruct
  revision: <commit-sha>         # pinned, not "main"
  files:
    - path: model.gguf
      sha256: <hash>
quant: Q4_K_M
size_gb: 42.5
context_length: 8192
notes: |
  Free-form.
```

**`pull.sh`** — downloads to `$LLM_DATA_ROOT/models/{id}/`, verifies sha256, idempotent.

**`README.md`** — model-card highlights, how it differs from sibling quants of the same base.

### 6.3 `configs/{config-id}.yaml`

Flat layout. Naming convention: `{runtime-id}__{model-id}__{preset}.yaml` (double underscore between components, hyphens within each component).

```yaml
id: vllm-cuda__llama3-70b-q4km__throughput
runtime: vllm-cuda                  # must match runtimes/<id>/
model: llama3-70b-q4km              # must match models/<id>/
description: Max throughput, TP=2, 8k context

serve:
  host: 127.0.0.1
  port: 8000
  args:                             # free-form map; the runtime's serve.sh interprets
    tensor-parallel-size: 2
    max-model-len: 8192
    gpu-memory-utilization: 0.9
    dtype: auto
  env:
    CUDA_VISIBLE_DEVICES: "0,1"
    HF_HOME: ${data_root}/cache/hf

readiness:
  timeout_seconds: 600
  endpoint: /v1/models
```

`serve.args` is the main playing field — what the user (or future UI) tweaks.

### 6.4 `benchmarks/{benchmark-id}/`

Benchmarks are **thin wrappers around preexisting tools**. No homegrown workload spec.

**`bench.yaml`:**

```yaml
id: vllm-bench-throughput
description: Sustained throughput via `vllm bench serve`
needs_server: true                  # default true; false skips the serve step
```

**`run.sh`** — invoked by the orchestrator with these env vars set:

- `LLM_ENDPOINT` — e.g. `http://127.0.0.1:8000/v1`
- `LLM_MODEL_ID` — the OpenAI model name to send in requests
- `LLM_OUTPUT_DIR` — where to write metrics and raw artifacts

The script shells out to whatever tool it wraps (`vllm bench`, `llama-bench`, `lm-eval`, `guidellm`, etc.), dumps native output into `$LLM_OUTPUT_DIR/raw/`, and writes a normalized `$LLM_OUTPUT_DIR/metrics.json` summary.

Example for `llama-bench` (which doesn't need a server — sets `needs_server: false`):

```bash
#!/usr/bin/env bash
set -euo pipefail
llama-bench -m "$LLAMA_MODEL_PATH" -p 512 -n 128 -o csv \
  > "$LLM_OUTPUT_DIR/raw/llama-bench.csv"
python "$(dirname "$0")/_normalize.py" "$LLM_OUTPUT_DIR" \
  > "$LLM_OUTPUT_DIR/metrics.json"
```

### 6.5 `state/`

- `active.yaml`: `{ config_id: "...", since: "<iso8601>" }`. Committed — your pinned daily driver is part of your documented setup.
- `running.json`: array of `{ config_id, pid, port, started_at, log_path }` (usually 0 or 1 entries). Gitignored.
- `history.jsonl`: append-only, one JSON object per line. Schema: `{ ts, action: "start|stop|switch|bench", config_id, ... }`. Gitignored.
- `logs/`: daily-driver serve logs, rotated by date. Gitignored.

## 7. Serve contract and orchestrator

### 7.1 Serve contract recap

Every runtime exposes the same three-script interface:

```
runtimes/{id}/build.sh                    # no args, idempotent
runtimes/{id}/serve.sh        --config <path>
runtimes/{id}/healthcheck.sh  --config <path>
```

Plus optional `version.sh` (no args, prints one line).

### 7.2 The orchestrator

One shared orchestrator lives in `scripts/_orchestrator.py` and is invoked by the CLI for both benchmark runs and daily-driver lifecycle. Pseudocode for `llm bench`:

```python
def bench(benchmark_id, config_id):
    cfg = load_config(config_id)
    bench = load_bench(benchmark_id)
    output_dir = mkdir_result_path(benchmark_id, config_id, utcnow_iso())

    write_snapshot(output_dir, cfg, bench)        # before doing anything

    server = None
    try:
        if bench.needs_server:
            server = spawn(runtimes[cfg.runtime].serve_sh,
                           args=["--config", cfg.path],
                           stdout=output_dir/"server.log",
                           stderr=STDOUT)
            wait_for_ready(server, cfg, timeout=cfg.readiness.timeout_seconds)

        env = {
            "LLM_ENDPOINT": f"http://{cfg.serve.host}:{cfg.serve.port}/v1",
            "LLM_MODEL_ID": cfg.model,        # each runtime's serve.sh sets --served-model-name to this
            "LLM_OUTPUT_DIR": str(output_dir),
        }
        rc = run(bench.run_sh, env=env,
                 stdout=output_dir/"client.log", stderr=STDOUT)
    finally:
        if server: stop(server)                   # SIGTERM, wait, SIGKILL on timeout

    finalize_snapshot(output_dir, rc)
```

`llm start <config>` and `llm switch <config>` reuse the same serve-spawn + wait-for-ready logic, but instead of running a benchmark they update `state/running.json` and return, leaving the server alive.

### 7.3 Daily driver via systemd (optional)

`llm default <config-id>` writes `state/active.yaml`.
`llm default --apply-systemd` additionally writes/updates a user unit at `~/.config/systemd/user/llm.service` that invokes the orchestrator's `llm start` against the active config. Combined with `loginctl enable-linger`, the daily driver starts when WSL boots and survives terminal logout.

systemd is **not** used for benchmarks — those are ephemeral and orchestrated directly by `llm bench`. systemd is only the auto-start mechanism for the pinned daily driver.

## 8. Per-run snapshot

Every benchmark run produces a self-contained results folder:

```
benchmarks/{benchmark-id}/results/{config-id}/{YYYY-MM-DDTHH-MM-SSZ}/
├── run.json
├── metrics.json
├── server.log
├── client.log
└── raw/
```

### 8.1 `run.json` schema

```json
{
  "schema_version": 1,
  "benchmark_id": "vllm-bench-throughput",
  "config_id": "vllm-cuda__llama3-70b-q4km__throughput",
  "started_at": "2026-05-15T18:30:00Z",
  "ready_at":   "2026-05-15T18:31:42Z",
  "bench_started_at": "2026-05-15T18:31:43Z",
  "bench_ended_at":   "2026-05-15T18:33:50Z",
  "stopped_at":       "2026-05-15T18:33:55Z",
  "exit_code": 0,

  "repo": { "commit": "abc1234", "dirty": false },

  "runtime": {
    "id": "vllm-cuda",
    "manifest_ref": "v0.7.3",
    "built_commit": "abc1234def...",
    "version_string": "vllm 0.7.3+cu124"
  },

  "model": {
    "id": "llama3-70b-q4km",
    "source_kind": "huggingface",
    "source_ref": "meta-llama/Meta-Llama-3-70B-Instruct@<sha>",
    "files": [{"path": "model.gguf", "sha256": "..."}]
  },

  "config_inline": { "...": "full copy of the resolved config yaml" },

  "hardware": {
    "cpu_model": "AMD Ryzen 9 7950X",
    "cpu_cores": 16,
    "ram_gb": 64,
    "gpus": [
      {"index": 0, "name": "NVIDIA RTX 4090", "vram_gb": 24,
       "driver": "560.94", "cuda": "12.6"}
    ]
  },

  "environment": {
    "os": "Windows 11 23H2 (Build 22631)",
    "wsl_distro": "Ubuntu-22.04",
    "wsl_kernel": "5.15.153.1-microsoft-standard-WSL2",
    "python": "3.11.9"
  }
}
```

Notes:

- **`config_inline` embeds the full resolved config**, not just a path. If you rename or edit a config later, old results still tell you exactly what was run.
- **`manifest_ref` vs `built_commit`** — the manifest says what you *wanted* to build; the build step records what was *actually* built. These can diverge if upstream moves a tag.

### 8.2 `metrics.json` schema

A flat dict of normalized metrics plus a `_meta` block:

```json
{
  "_meta": { "schema_version": 1, "source_tool": "vllm bench serve" },
  "requests_per_sec": 18.3,
  "tokens_per_sec_in":  812.4,
  "tokens_per_sec_out": 1543.2,
  "ttft_p50_ms": 124,
  "ttft_p95_ms": 287,
  "e2e_p50_ms":  3120,
  "e2e_p95_ms":  4810
}
```

Benchmarks can add new metric keys freely. A future UI graphs whatever keys exist. The contract is "flat dict of numbers, plus `_meta`".

## 9. File-format conventions

| Author | Format | Examples |
|---|---|---|
| Human-authored | **YAML / Markdown** | `configs/*.yaml`, `runtimes/*/manifest.yaml`, `models/*/manifest.yaml`, `benchmarks/*/bench.yaml`, `state/active.yaml`, `paths.yaml`, `requirements.yaml`, `docs/*.md` |
| Machine-emitted | **JSON / JSONL** | `run.json`, `metrics.json`, `state/running.json`, `state/history.jsonl`, results `raw/*` (when tool-native) |
| Auto-generated from yaml | **Markdown** | `specs.md`, `requirements.md` |

YAML for things humans edit (comments, multi-line strings); JSON for things machines emit and consume (no YAML dep needed for a future webui).

## 10. `specs.md` — auto-generated

`specs.md` is regenerated by `llm specs` from data collected by `scripts/_specs.py`. It has a marked auto block and a preserved notes region.

```markdown
# System Specs

<!-- AUTO-GENERATED: do not edit between markers. Run `llm specs` to regenerate. -->
<!-- llm:specs:start -->
_Generated: 2026-05-15T18:30:00Z_

## Host
- **OS:** Windows 11 23H2 (Build 22631)
- **CPU:** AMD Ryzen 9 7950X (16C / 32T)
- **RAM:** 64 GB

## GPU
| Idx | Name | VRAM | Driver |
|---|---|---|---|
| 0 | NVIDIA RTX 4090 | 24 GB | 560.94 |

CUDA runtime: 12.6

## WSL
- **Distro:** Ubuntu-22.04
- **Kernel:** 5.15.153.1-microsoft-standard-WSL2
- **Memory available:** 48 GB
- **Systemd:** enabled

## Storage layout
- Repo: `/mnt/c/Private/Projects/LocalLLM/`
- Data root: `/home/melih/llm/`
<!-- llm:specs:end -->

## Notes
<!-- Free-form. Preserved across regenerations. -->
- Power plan: "Ultimate Performance"
- Resizable BAR enabled in BIOS
```

`llm specs` rewrites only the bytes between `<!-- llm:specs:start -->` and `<!-- llm:specs:end -->`. Everything else is preserved verbatim. If markers are missing, the command refuses to overwrite without `--force`.

### Detection sources

| Field | Source |
|---|---|
| OS / build | `cmd.exe /c ver` (via WSL interop) |
| CPU model / cores | `/proc/cpuinfo`, `lscpu` |
| RAM total | `/proc/meminfo` |
| GPU(s) | `nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader` |
| CUDA runtime | `nvidia-smi` header, or `nvcc --version` if present |
| WSL distro | `/etc/os-release` |
| WSL kernel | `uname -r` |
| WSL memory available | `/proc/meminfo` |
| Systemd | `/etc/wsl.conf` parse + `systemctl is-system-running` |
| Repo path | `git rev-parse --show-toplevel` |
| Data root | `paths.yaml` |

Each detection degrades gracefully if a tool is missing (reports "not detected" rather than crashing).

## 11. `requirements.yaml` / `requirements.md`

External prerequisites that must exist on the machine. Source of truth is `requirements.yaml`; `requirements.md` is auto-rendered.

### 11.1 `requirements.yaml` schema

```yaml
- id: cuda-driver
  name: NVIDIA CUDA Driver (Windows host)
  why: GPU passthrough into WSL2
  verify:
    cmd: nvidia-smi
    version_regex: 'Driver Version: ([\d.]+)'
    min: "535.0"
  install_hint: "https://www.nvidia.com/Download/index.aspx"

- id: python
  name: Python
  why: Base interpreter for runtime venvs and the CLI
  verify:
    cmd: python3 --version
    version_regex: 'Python ([\d.]+)'
    min: "3.11"
  install_hint: "apt install python3.11 python3.11-venv"

- id: hf-cli
  name: huggingface-hub CLI
  why: Used by models/*/pull.sh
  verify:
    cmd: huggingface-cli --version
    version_regex: '([\d.]+)'
    min: "0.20.0"
  install_hint: "pip install -U huggingface_hub[cli]"

- id: build-essential
  name: build-essential + cmake
  why: Building llama.cpp and similar native runtimes
  verify:
    cmd: gcc --version
    version_regex: 'gcc.*?([\d.]+)'
    min: "11.0"
  install_hint: "apt install build-essential cmake"
```

Scope rule: **only cross-cutting requirements** go here. Anything specific to a single runtime belongs in that runtime's `README.md` and `build.sh`.

### 11.2 `requirements.md`

Auto-rendered from `requirements.yaml` by `llm doctor render-requirements`. Always reflects the yaml. Committed.

## 12. CLI surface — `llm`

Lives at `scripts/llm`, implemented in Python 3.11+ with Typer. No deep dependencies — pyyaml, httpx, rich, typer, plus stdlib.

```
llm init                                 # read paths.yaml, create $LLM_DATA_ROOT layout
llm list [runtimes|models|configs|benchmarks]   # default: everything
llm status                               # what's running, daily driver, ports, uptime
llm doctor                               # checks requirements.yaml + sanity (paths, ports)
llm doctor render-requirements           # regenerate requirements.md from requirements.yaml
llm specs                                # regenerate auto block in specs.md
llm specs --check                        # diff fresh detection against specs.md, nonzero on drift
llm specs --print                        # print detection only, don't touch the file

# Acquiring things
llm build <runtime-id>                   # runs runtimes/<id>/build.sh
llm pull  <model-id>                     # runs models/<id>/pull.sh

# Daily-driver lifecycle
llm start  <config-id>                   # stops current, starts new, waits for ready
llm stop                                 # SIGTERM the running serve
llm switch <config-id>                   # alias for stop + start
llm default <config-id>                  # pin in state/active.yaml
llm default --apply-systemd              # install/update systemd user unit for active
llm logs [--follow]                      # tail the running serve's log

# Benchmarking
llm bench <benchmark-id> --config <config-id>
llm bench <benchmark-id> --matrix 'vllm-cuda__*'     # against multiple configs by glob
llm results <benchmark-id> [--config <config-id>] [--last N]    # tabular summary

# Diagnostics
llm config show <config-id>              # render resolved config (defaults applied)
llm config validate                      # check all configs reference real runtimes+models
```

### 12.1 `--json` flag

Every read-only command (`list`, `status`, `results`, `config show`) supports `--json` for structured output. This is the contract a future TUI or webui will consume.

### 12.2 Installation

A small `install.sh` creates `~/llm/.cli-venv/`, installs `requirements.txt` into it, and writes a shim at `~/.local/bin/llm` that activates the venv and exec's the script. Uninstall is `rm`.

## 13. Forward-compatibility commitments

Small choices made now to keep TUI/web additions purely additive:

1. **`--json` on every read-only command.** UI consumes JSON, not formatted text.
2. **`state/running.json` is the single source of truth** for "what's live right now". UI polls or watches this file; never inspects `ps` directly.
3. **`state/history.jsonl` is append-only**, one event per state change. UI renders an activity feed by reading it.
4. **`metrics.json` is a flat dict of numbers plus `_meta`.** UI graphs by metric name without per-benchmark adapters.
5. **No symlinks in result paths.** Timestamps sort lexicographically; UI gets newest-first by reverse-sorting directory listings.

## 14. Discipline rules

### 14.1 Docs are part of the change

When a workflow changes — e.g. adding a model now requires an extra step — the relevant `docs/add-a-*.md` is updated **in the same commit** as the code change. A HOWTO that's more than two weeks stale relative to actual practice is treated as a bug.

The `docs/` HOWTOs are:

- `docs/wsl-setup.md` — one-time WSL2 + systemd + CUDA driver setup
- `docs/repo-conventions.md` — this design doc, distilled to a working reference
- `docs/add-a-runtime.md` — add a new runtime folder + the three scripts
- `docs/add-a-model.md` — add a model manifest + pull.sh
- `docs/add-a-config.md` — write a new config yaml
- `docs/add-a-benchmark.md` — wrap a new benchmark tool
- `docs/runtimes/{runtime-id}.md` — per-runtime deep notes as needed

Each HOWTO follows the template: **prerequisites → steps → verification → common pitfalls**.

### 14.2 Requirements are part of the change

When a script or workflow gains a new external dependency, `requirements.yaml` is updated in the same commit. `requirements.md` is regenerated by `llm doctor render-requirements` and committed alongside.

## 15. Out of scope / future work

- **TUI dashboard** (textual or rich) — additive on top of the JSON contract.
- **Web UI** (FastAPI + minimal frontend or HTMX) — additive; would render `arg_schema` into a form, graph `metrics.json` history, expose a chat playground against the daily-driver endpoint.
- **Multi-host** — `specs.md` becomes `specs/{host-id}.md`; `run.json` records `host_id`. Folder layout otherwise unchanged.
- **Auto-discovery of new HF models** — out of scope; model adds remain manual.
- **Distributed benchmarks** (multi-machine) — out of scope.
- **Comparing results across configs** programmatically (regression detection, leaderboards) — possible later from `metrics.json` history; not in v1.
