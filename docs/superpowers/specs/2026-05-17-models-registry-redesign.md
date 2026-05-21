# LocalLLM Models Registry Redesign

_Date: 2026-05-17_
_Status: Approved by user, ready for implementation planning_

## 1. Purpose

Replace the per-model `manifest.yaml` + `pull.sh` abstraction with a single local **model registry** populated directly from Hugging Face (or local paths) by the CLI. Hugging Face already is the de-facto registry for weights; the repo shouldn't carry a parallel catalog of YAML stubs and bespoke shell scripts. The CLI becomes the abstraction layer: it ingests an HF URL (or a local path), records the result in a JSON registry under the data root, and lets configs reference models by stable id.

## 2. Problems solved

- **`pull.sh` is one-liner boilerplate.** Every model's pull script is effectively `hf download <repo> --include <file> --local-dir $LLM_MODELS/<id>`. Tracking that boilerplate per model adds no value but adds maintenance.
- **Catalog and weights live in two places.** Today the catalog ships in git (`models/<id>/manifest.yaml`) while the weights live under `$LLM_MODELS/`. The two can drift; nothing forces them to agree.
- **Configs duplicate model paths.** A config sets `serve.params.gguf_path: ${data_root}/models/<id>/<file>`, repeating information the model entry already implies.
- **No format-vs-runtime safety net.** A config that pairs a GGUF with a vLLM runtime fails at serve time, not validation time.
- **Multi-file artifacts are second-class.** Split GGUF shard sets and safetensors directories have no first-class representation; users hand-roll the paths.
- **Ad-hoc local weights have no place.** If you already downloaded weights elsewhere, the current abstraction makes you write a fake `pull.sh` or copy them into the expected layout.

## 3. Goals

- **One registry per machine** at `$LLM_MODELS/registry.json` is the single source of truth for installed models. Not tracked in git.
- **One CLI verb to fetch from HF**: `loco model pull <url>` resolves the URL, downloads the artifact via `hf download`, and records a complete registry entry.
- **One CLI verb to register pre-existing local weights**: `loco model add <id> <path> --format <fmt>` symlinks them under `$LLM_MODELS/<id>/` and records the entry.
- **`models/` directory in the repo goes away.** No `manifest.yaml`, no `pull.sh`, no `README.md` per model.
- **Strict-by-default URL handling.** If the format can't be inferred unambiguously, `pull` errors out and asks for `--format`/`--include`. No silent fallbacks, no "unknown" stub state.
- **Configs reference models by id and use a `${model_path}` template** in `serve.params` values. No invisible auto-wiring; the path appears in the config text.
- **Format-vs-runtime compatibility checked at `loco config validate`.** A new `accepts_formats` field on runtime manifests gates which models that runtime will accept.
- **Multi-file artifacts are first-class.** Shard sets and safetensors directories are represented uniformly via `artifact.primary` (the path the runtime should consume) and `artifact.files` (the full set).

## 4. Non-goals

- **HF authentication management.** `HF_TOKEN` is read from the environment if present; the CLI does not run `huggingface-cli login`, store credentials, or prompt for a token. Gated/private repos that 401/403 surface as clear errors with a hint.
- **A second discovery state.** No `unknown` registry rows. Either we can record a complete entry or we refuse and tell the user what to disambiguate.
- **A `verify` subcommand.** sha256 verification happens during `pull` only, when HF publishes a hash for the file (LFS). No standalone re-verify.
- **A model `rebuild`/drift-detection analogue to runtimes.** `pull <id>` re-resolves and re-downloads, and that's enough.
- **Multi-source backends beyond `hf` and `local`.** No direct-URL, no Ollama, no ModelScope in v1. The `source.kind` discriminator leaves room to add them later.
- **Automatic ingestion of legacy `models/<id>/` dirs.** A one-shot manual `loco model add` per local set is the migration path.
- **Per-config model variants.** A model id is one specific artifact (one file for GGUF, one directory for safetensors). Different quants are different ids.
- **Remote model registry / browsing / search.** The CLI does not list HF models or recommend choices.
- **Concurrent pulls or registry locking.** Single-user, single-machine assumed. Atomic writes only.

## 5. Architecture

### 5.1 Registry file

Path: **`$LLM_MODELS/registry.json`**. Created on first `loco model pull|add`. Writes are atomic via `tmp + os.replace`.

```json
{
  "version": 1,
  "models": {
    "<model-id>": {
      "format": "gguf" | "safetensors-dir",
      "source": { ... source-kind specific ... },
      "artifact": {
        "primary": "<relative path under $LLM_MODELS/<model-id>/>",
        "files": ["<rel path>", "..."],
        "total_size_bytes": 12345,
        "sha256": { "<rel path>": "<hex>", "...": "..." }
      },
      "metadata": {
        "display_name": "...",
        "license": "...",
        "ctx_length": 32768
      },
      "installed_at": "2026-05-17T20:00:00Z"
    }
  }
}
```

### 5.2 Source kinds

**`hf`** — fetched from Hugging Face via `hf download`:

```json
"source": {
  "kind": "hf",
  "repo": "unsloth/Qwen3.6-235B-A22B-GGUF",
  "revision": "main",
  "include": ["*UD-Q4_K_XL*"],
  "exclude": []
}
```

`include`/`exclude` are stored verbatim so re-pulls are deterministic.

**`local`** — symlinked from a path the user already has:

```json
"source": {
  "kind": "local",
  "original_path": "/home/me/llm/staging/my-finetune"
}
```

### 5.3 Artifact representation

`artifact.primary` is the relative path the runtime consumes:

| Layout | `artifact.primary` | `artifact.files` |
|---|---|---|
| GGUF single file | `weights.gguf` | `["weights.gguf"]` |
| GGUF split shard set | `model-00001-of-00010.gguf` | `["model-00001-of-00010.gguf", ...]` |
| safetensors directory | `.` | `["config.json", "tokenizer.json", "model-*.safetensors", ...]` |

`artifact.sha256` maps each file to its hex hash when known (HF LFS metadata provides this for free; absent for non-LFS files).

### 5.4 Runtime manifest extension

Each runtime manifest gains one optional field:

```yaml
# runtimes/llamacpp/manifest.yaml
accepts_formats: [gguf]
```

Semantics:

- Non-empty list → runtime consumes a model; configs **must** set `model:`.
- Empty list (`accepts_formats: []`) → runtime needs no model; configs **must omit** `model:` (smoke runtimes like `stub-runtime`).
- Field absent → treated as empty (backwards-compatible).

### 5.5 Config templating

Configs use `${model_path}` (and the existing `${data_root}`, `${models_dir}`, `${runtimes_dir}`) inside `serve.params` values:

```yaml
# configs/llamacpp__unsloth-qwen3.6-235b-a22b__ud-q4-k-xl.yaml
runtime: llamacpp
model: unsloth-qwen3.6-235b-a22b__ud-q4-k-xl
serve:
  host: 127.0.0.1
  port: 8080
  params:
    gguf_path: "${model_path}"
    n_gpu_layers: -1
    ctx: 8192
```

`${model_path}` resolves to `$LLM_MODELS/<model-id>/<artifact.primary>`. Resolution happens in `core/config_resolve.py`, in the same pass that already handles `${data_root}`. Unknown tokens are hard errors.

Sibling tokens reserved but not implemented in v1 (added when a real need appears):

- `${model_dir}` → `$LLM_MODELS/<model-id>/`
- `${model_file}` → `<artifact.primary>` (filename only)

### 5.6 URL parsing

Accepted shapes (case-insensitive scheme; `huggingface.co` or `hf.co`):

```
https://huggingface.co/<owner>/<repo>
https://huggingface.co/<owner>/<repo>/tree/<rev>
https://huggingface.co/<owner>/<repo>/blob/<rev>/<path>
https://huggingface.co/<owner>/<repo>/resolve/<rev>/<path>
```

Parser output: `(repo, revision_or_main, file_or_none)`.

### 5.7 Format inference at pull time

```text
url has a file path:
  file ends in .gguf            → format = gguf
  any other extension           → error (use --format and/or --include)

url has no file path:
  fetch repo file list via HF API
  multiple *.gguf quants present (different quant families)
                                → ambiguous → error with hint
  exactly one *.gguf (single file or one shard family)
                                → format = gguf
  files include config.json and *.safetensors and no *.gguf
                                → format = safetensors-dir
  mixed (e.g. gguf + safetensors)
                                → error with hint

--format and --include flags always override inference. A successful
--include that matches one quant family (single file or all shards of one
NNNNN-of-NNNNN set) is treated as one model; that's the "different quants
are different ids" rule.
```

Errors always include the suggested flags.

### 5.8 HF API client

A small `core/hf_client.py` using stdlib `urllib`:

- `GET https://huggingface.co/api/models/<repo>/revision/<rev>` for repo metadata, license tag, full file list, LFS sha256s and sizes.
- `Authorization: Bearer $HF_TOKEN` only when `HF_TOKEN` is set in env.
- Timeouts: 15s connect, 60s total. Network errors during the metadata fetch fail the `pull` (no partial registry write).

The `hf download` subprocess remains responsible for the actual bytes.

### 5.9 Local registration (`loco model add`)

```bash
loco model add <id> <path> --format <gguf|safetensors-dir>
```

- Path must exist.
- `gguf`: path is a file or a directory containing a `*-00001-of-NNNNN.gguf` shard set.
- `safetensors-dir`: path is a directory containing `config.json`.
- Files are **symlinked** into `$LLM_MODELS/<id>/`. If symlink creation fails (e.g. the filesystem rejects symlinks), fall back to copy and print a one-line `[info]` notice to stderr; do not fail the command.
- Registry entry uses `source.kind: local` with `original_path` recorded for traceability.

### 5.10 CLI command surface

```text
loco model list [--json]
loco model info <id> [--json]
loco model pull <url-or-id>
        [--format gguf|safetensors-dir]
        [--include PATTERN ...]
        [--exclude PATTERN ...]
        [--id NEW_ID]
        [--force]
loco model add <id> <path> --format <gguf|safetensors-dir>
loco model uninstall <id> [--purge] [--yes]
```

`loco model list` table: id, format, source kind, total size, present (files on disk?), installed_at.

## 6. CLI flows

### 6.1 Pull from a clear GGUF URL

```bash
loco model pull \
  https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/blob/main/Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf
```

Steps:

1. Parse URL → `(repo="unsloth/Qwen3.6-235B-A22B-GGUF", revision="main", file="...UD-Q4_K_XL-00001-of-00010.gguf")`.
2. Derive id: `unsloth-qwen3.6-235b-a22b__ud-q4-k-xl` (org slug + filename quant slug, shard suffix stripped).
3. Fetch HF metadata → license, repo description, LFS hashes for all matching shards.
4. Compute `--include` patterns automatically: `*UD-Q4_K_XL*` (covers all shards of this quant).
5. `hf download <repo> --revision <rev> --include <pat> --local-dir $LLM_MODELS/<id>/` with `HF_HOME=$LLM_CACHE/hf`.
6. Build artifact: `primary` = first shard, `files` = full sorted shard list, `sha256` = per-file map.
7. Verify each LFS sha256 (cheap given file sizes; mismatch aborts and leaves files on disk).
8. Atomic registry write.

### 6.2 Pull from an ambiguous repo

```bash
loco model pull https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF
# error: this HF repo contains multiple GGUF quants. Re-run with one of:
#   --include "*UD-Q4_K_XL*"      (and --id <suggested>)
#   --include "*Q5_K_M*"          (...)
# Pick a single quant; we won't auto-pick for you.
```

No registry entry is written.

### 6.3 Local registration

```bash
loco model add my-finetune ~/llm/staging/my-finetune --format safetensors-dir
```

Steps: validate path → mkdir `$LLM_MODELS/my-finetune/` → symlink children → record entry with `source.kind=local`.

### 6.4 Refresh / repair an existing id

```bash
loco model pull unsloth-qwen3.6-235b-a22b__ud-q4-k-xl
```

Steps: look up source from registry → re-run `hf download` (resumes partial files) → re-verify hashes → rewrite registry entry timestamp.

### 6.5 Uninstall

```bash
loco model uninstall my-finetune --purge --yes
```

Removes registry row; with `--purge`, removes `$LLM_MODELS/<id>/` (which for local-add is just symlinks pointing at the user's untouched originals).

## 7. Validation rules (added/changed)

`loco config validate` runs these rules in addition to today's:

1. `runtime:` resolves; runtime manifest loads cleanly.
2. If `runtime.accepts_formats` is non-empty, `model:` is required.
3. If `runtime.accepts_formats` is empty (or absent), `model:` must not be set.
4. When `model:` is set, it must resolve to a registry entry under `$LLM_MODELS/registry.json`.
5. `model.format` must be in `runtime.accepts_formats`.
6. `${model_path}` (and any future `${model_*}` tokens) only resolve when `model:` is set; using them without `model:` is an error.
7. All `${...}` tokens in `serve.params` values must resolve; unknown tokens are errors.
8. Per-param type validation against `runtime.serve_schema` (unchanged).
9. Advisory warnings (do not fail validation):
   - Runtime is not installed.
   - `model.artifact.primary` is missing on disk under `$LLM_MODELS/<id>/`.

## 8. Migration

In-repo changes:

1. **Delete** `models/stub-model/` (and any other tracked model directories) entirely.
2. **Rename** `configs/stub-runtime__stub-model__default.yaml` → `configs/stub-runtime__default.yaml`; remove the `model:` line.
3. **Add** `accepts_formats: [gguf]` to `runtimes/llamacpp/manifest.yaml`.
4. **Add** `accepts_formats: []` to `runtimes/stub-runtime/manifest.yaml`.
5. **Delete** `src/llm_cli/core/registry.py`'s `ModelRecord`, `discover_models`, `get_model`, `validate_model_layout` (replaced by registry-backed lookups).
6. **Rewrite** `src/llm_cli/commands/model_cmd.py` against the new registry module.
7. **Update** `docs/add-a-model.md` to describe `loco model pull <url>` / `loco model add <id> <path>` and the `${model_path}` template.
8. **Update** `docs/repo-conventions.md` (drop the `models/{id}/` row; mention `$LLM_MODELS/registry.json`).
9. **Update** the example llamacpp config (untracked today) to use `${model_path}` and the new model id once the user runs `loco model pull` for their preferred quant.

User-side migration:

- Existing `$LLM_MODELS/<id>/` directories not in the registry are inert until the user runs `loco model add <id> <path> --format <fmt>` to register them.

## 9. Testing approach

- **Unit:**
  - URL parser: valid URLs (`blob`, `resolve`, `tree`, bare repo, hf.co short host) and invalid URLs (wrong scheme, wrong host, malformed path).
  - HF API client: parses real-shape responses (license, siblings, LFS sha256); honors `HF_TOKEN` env when present.
  - Registry I/O: atomic write semantics; tolerates a missing file (returns empty); rejects malformed JSON loudly.
  - Template resolution: `${model_path}` resolves, errors on missing model, errors on unknown token.
  - `derive_id` from URL components.
  - Format inference cases (clear gguf, all-gguf-repo, safetensors repo, mixed repo).
- **Integration (Typer + tmpdir):**
  - `loco model add` with a real tmpdir → assert symlinks under `$LLM_MODELS/<id>/`, registry row present, `source.kind=local`.
  - `loco model pull <url>` happy path with HF client patched and `hf download` subprocess patched.
  - `loco model pull <ambiguous-url>` exits 1, registry unchanged, hint mentions `--include` and `--format`.
  - `loco model pull <existing-id>` re-runs `hf download` with stored args; updates `installed_at`.
  - `loco model uninstall --purge` removes registry row and files.
  - `loco config validate`:
    - llamacpp + missing `model:` → error.
    - stub-runtime + erroneous `model:` → error.
    - llamacpp + safetensors model → format-mismatch error.
    - config with `${model_path}` but no `model:` → error.
    - happy path → ok, with warning when runtime not installed.
  - `loco serve` template expansion writes the right env to a fake serve.sh script (use the existing test harness).

## 10. Open follow-ups (deferred)

- HF token UX (login, gated repo flow, scoped tokens).
- `verify` / `rebuild` subcommands and revision-drift detection.
- Direct-URL and Ollama source kinds.
- `${model_dir}` / `${model_file}` template tokens (add when first config needs them).
- Per-runtime model adapter notes (e.g., per-runtime chat templates, sampler defaults) — likely a separate spec if needed.

## 11. Cross-references

- Settings & data layout: [`2026-05-17-settings-and-setup-redesign.md`](2026-05-17-settings-and-setup-redesign.md).
- Runtime manifest baseline this builds on: [`2026-05-17-runtime-manifest-and-installs.md`](2026-05-17-runtime-manifest-and-installs.md).
- Serve/stop/switch lifecycle: [`2026-05-17-lifecycle-and-serve.md`](2026-05-17-lifecycle-and-serve.md).
- Original layout (superseded for the `models/` section): [`2026-05-15-localllm-scaffolding-design.md`](2026-05-15-localllm-scaffolding-design.md).
