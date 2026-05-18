# vLLM runtime

Official `vllm` runtime integration for this scaffold.

- Installs `vllm` into `${LLM_RUNTIMES}/vllm/venv`
- Runs `vllm serve` with typed params from `params.yaml`
- Healthcheck probes `GET /v1/models`
