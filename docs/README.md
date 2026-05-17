# LocalLLM Documentation

Start with the root [`README.md`](../README.md) for `llm setup` and the CLI command table.
Machine-local settings live at `~/.config/llm/config.yaml` and are managed with
`llm setup` / `llm settings ...`; repo `configs/*.yaml` remain launch units.

| Document | Purpose |
|---|---|
| [`wsl-setup.md`](wsl-setup.md) | One-time WSL2 + systemd + CUDA driver setup |
| [`repo-conventions.md`](repo-conventions.md) | Layout, settings/config split, discovery, and commit boundaries |
| [`add-a-runtime.md`](add-a-runtime.md) | Add `runtimes/{id}/` and hook up `build.sh` |
| [`add-a-model.md`](add-a-model.md) | Add `models/{id}/` and `pull.sh` |
| [`add-a-config.md`](add-a-config.md) | Add `configs/*.yaml` and validate |
| [`add-a-benchmark.md`](add-a-benchmark.md) | Add `benchmarks/{id}/` layout |
| [`lifecycle.md`](lifecycle.md) | `llm serve` / `stop` / `switch` / `status` / `logs` |

(Per-runtime deep dives can live under `docs/runtimes/{runtime-id}.md` when needed.)
