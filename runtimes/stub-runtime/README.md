# stub-runtime

Minimal runtime package for discovery, `loco build`, layout validation, and **`loco serve`** smoke tests.

- **`serve.sh`** — small Python TCP server on `LLM_SERVE_HOST` / `LLM_SERVE_PORT`; replies with `hello` per connection; exits cleanly on SIGINT/SIGTERM.
- **`healthcheck.sh`** — exits 0 when that TCP port accepts a connection (used by the CLI readiness loop).

Replace with a real backend (vLLM, llama.cpp, …) while keeping the same script names and env contract.
