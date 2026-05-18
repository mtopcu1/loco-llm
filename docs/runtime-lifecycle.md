# Runtime lifecycle: install, uninstall, rebuild

This document describes **`llm runtime`** — how runtimes are installed under the WSL data root, how that ties into **`serve.params`**, and how drift is detected. Manifests distinguish **`kind: official`** (build scripts + install/rebuild) from **`kind: custom`** (author-time scaffolding via **`llm runtime setup`**, no **`build.sh`**). For serve modes (`foreground` / background / systemd), see [`lifecycle.md`](lifecycle.md).

## Commands

| Command | Purpose |
|---|---|
| `llm runtime list` | Runtimes discovered under `runtimes/*/manifest.yaml`. |
| `llm runtime info <id>` | Manifest summary, install record, drift warnings (script/schema changes since install). |
| `llm runtime setup` | Wizard: install an **`official`** runtime or scaffold/register a **`custom`** one in-repo. |
| `llm runtime install <id>` | Interactive or `--yes` install (**official only**): build params → `build.sh` → optional `verify.sh` → write `.installed`. |
| `llm runtime uninstall <id>` | Remove the `.installed` marker; **`--purge`** additionally deletes `$LLM_RUNTIMES/<id>/`. |
| `llm runtime rebuild <id>` | **Official only.** Re-run install using **stored** build params; **`--reset`** discards stored params and prompts again. |

Examples:

```bash
llm runtime install stub-runtime --yes
llm runtime info stub-runtime
llm runtime rebuild llamacpp --reset
```

## The `.installed` record

After a successful install, the CLI writes:

**`$LLM_RUNTIMES/<runtime-id>/.installed`**

(JSON, sorted keys.) It typically includes:

| Field | Meaning |
|---|---|
| `runtime_id` | Runtime id. |
| `installed_at` | UTC timestamp of install. |
| `build_params` | Coerced build parameters used for that install. |
| `build_sh_sha256` | Hash of `runtimes/<id>/build.sh` at install time. |
| `verify_passed` | Whether `verify.sh` ran and exited 0. |
| `schema_hash` | Hash of the manifest’s build/serve schema at install time. |
| `kind` | **`official`** (built runtime) or **`custom`** (author-scaffolded; no build/rebuild). |

`llm runtime info` compares current files/manifest to these fields and may warn when **`build.sh`** or the **schema** drifted — informational until you **`rebuild`** (optionally **`--reset`**).

## Custom runtimes (`kind: custom`)

**`llm runtime install`** and **`llm runtime rebuild`** refuse **`kind: custom`** — there is no compiled artifact to rebuild. Edit files under `runtimes/<id>/` or use **`llm runtime setup`** again if you need to re-register.

## Build params vs serve params

| Phase | Who chooses values | Where they live |
|---|---|---|
| **Build** | User at **`llm runtime install`** (prompts, `--param`, or `--yes` defaults) | Stored in `.installed` as `build_params`; exported as **`LLM_BUILD_*`** to `build.sh`. |
| **Serve** | Author of **`configs/*.yaml`** under `serve.params` | Validated per manifest `serve:` schema at **`llm serve`** / **`llm switch`**; mapped to env for `serve.sh` / `healthcheck.sh`. |

Changing serve knobs does not require a rebuild unless your runtime conflates them; changing build flavor or jobs does.

## Pre-flight: `llm doctor --runtime <id>`

`llm doctor --runtime <id>` runs universal checks plus manifest **`requires`** entries relevant to the resolved **build** params (honoring **`when:`**). Use it before a long `install` or when CUDA/toolchain issues are suspected.

With no `--runtime`, `llm doctor` runs **`requirements.yaml`** checks plus manifest **`requires`** for **installed** runtimes only. **`--all`** adds deps for every discovered runtime regardless of install state.

## Why serve refuses without `.installed`

**`llm serve`** and **`llm switch`** require an install record so the CLI knows the runtime is registered under the current manifest-driven contract (**official** builds + **`custom`** registrations both write `.installed`). If `.installed` is missing, the command exits with an error and hints **`llm runtime install <id>`** or **`llm runtime setup`** for custom stacks.

## See also

- [`wizards.md`](wizards.md), [`add-a-runtime.md`](add-a-runtime.md)
- Spec: [`superpowers/specs/2026-05-17-runtime-manifest-and-installs.md`](superpowers/specs/2026-05-17-runtime-manifest-and-installs.md)
- Serve/stop/switch/logs: [`lifecycle.md`](lifecycle.md)
