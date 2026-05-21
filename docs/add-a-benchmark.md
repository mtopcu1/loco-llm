# HOWTO: add a benchmark

A **benchmark** is a folder under `benchmarks/{benchmark-id}/` with metadata and a `run.sh` entrypoint. Full orchestration (`loco bench`, env injection) is a later milestone; today the layout is fixed so **`loco list benchmarks`** and docs stay consistent.

## 1. Create the folder

```text
benchmarks/my-bench/
  README.md
  bench.yaml
  run.sh
  results/                  # optional; created by runs
```

## 2. Write `bench.yaml`

```yaml
id: my-bench
description: Short summary for `loco list`
needs_server: true           # false if the tool benchmarks GGUF directly, etc.
```

## 3. Implement `run.sh`

Use `set -euo pipefail`. Future `loco bench` will set variables such as `LLM_ENDPOINT`, `LLM_MODEL_ID`, and `LLM_OUTPUT_DIR` (see design spec §6.4). Until then, you can invoke your tool manually with the same layout you plan to script.

**Example stub** (writes a placeholder result):

```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p results
echo '{"ok":true}' > results/dev.json
```

## 4. Verify

```bash
loco list benchmarks
```

## See also

- [`repo-conventions.md`](repo-conventions.md)
- [Design spec §6.4](superpowers/specs/2026-05-15-localllm-scaffolding-design.md)
