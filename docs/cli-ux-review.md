# CLI UX review (manual exploration)

Notes from interactive testing via WSL against a live install (`loco` **0.1.0**). Grouped for triage.

---

## 1. Bugs

_No confirmed crash/data-loss bugs from this pass._

**Behavior that may surprise integrators (consider fixing or documenting explicitly):**

- **Readiness vs model load:** `healthcheck.sh` only checks **TCP connect** to `LLM_SERVE_HOST:LLM_SERVE_PORT`. **`loco serve`** / **`loco switch`** can print **`running`** while **`llama-server`** is still loading weights, so **`curl /v1/...`** may fail or stall briefly. Observed after **`loco switch`** back to a large GGUF: status showed **running** while **`/v1/models`** still reflected the previous model until load finished (~tens of seconds).

**Policy / exit-code semantics (promote to bug if you want strict tooling guarantees):**

- **`loco doctor`** exits **non-zero** when **`nvcc`** is missing, even if the CUDA **driver** is OK and a prebuilt GPU **`llama-server`** runs fine. Scripts using `loco doctor && …` fail without installing optional toolchain.

- **`loco config validate`** exits **0** while emitting **warnings** (e.g. config references a runtime that is **not installed**). CI may treat the repo as fully healthy.

---

## 2. Bad UX

- **`loco` with no subcommand:** exits **2** and dumps the full multi-panel help. A one-line hint (“Try `loco list`, `loco serve <config-id>`, or `loco --help`”) would reduce noise.

- **Truncated table IDs (`loco list`):** long config/model IDs show as **`…`**, awkward for copy-paste into **`loco serve`** / **`loco switch`**. Mitigation exists (**`loco list --json`**, **`loco model list --json`**) but is easy to miss—call it out in **`--help`** or add **`--full`**.

- **Thinking-style chat templates:** **`POST /v1/chat/completions`** may return **`choices[].message.content` empty** while **`reasoning_content`** holds the visible text. Clients that only read **`content`** look broken—document in a cookbook / README note.

- **Server logs on malformed JSON:** bad HTTP clients produce **`srv … got exception`** lines—noisy when tailing **`loco logs`** during bring-up.

- **Duplicate `loco serve` error wrapping:** the “already running in background; use …” message can split awkwardly across terminal width.

- **Rich line-wrapping splits identifiers:** at typical widths, **`loco config validate`** may break a long **`ok <config-id>`** line so **`__default`** wraps as **`__de`** / **`fault`**. Same pattern on **`loco serve`** / **`loco switch`** success lines (**`running …`** / **`port`** / **`8080`**). Hurts scanning and copy-paste.

- **`loco model pull` success hint:** the **`model:`** line wraps so the model id continues on the next line—easy to misread as two separate instructions.

---

## 3. Minor (typos, unclear copy, polish)

- **Top-level `--help`:** **`doctor`** row spacing/alignment looks slightly off vs other commands.

- **Doctor:** **`nvcc`** hint points at generic NVIDIA docs; one clause that **driver-only + prebuilt binary** setups are common for inference would set expectations.

- **`loco model pull`:** unauthenticated Hub warning is fine; could add **“set `HF_TOKEN` if downloads throttle”** once in docs so first-time users aren’t alarmed.

---

## Lifecycle test pass (2026-05-18)

Executed in WSL against `/mnt/c/Private/Projects/local-llm-scaffold`:

| Step | Result |
|------|--------|
| **`loco stop`** | Stopped **`llamacpp__unsloth-qwen3.6-35b-a3b__ud-q4-k-xl__default`**; **`loco status`** → not running. |
| **`loco model pull`** | Pulled **`TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF`** **`tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`** (~26s). Registered id **`thebloke-tinyllama-1.1b-chat-v1.0__tinyllama-1.1b-chat-v1.0.q4-k-m`**. |
| **New config** | Added **`configs/llamacpp__thebloke-tinyllama-1.1b-chat-v1.0__tinyllama-1.1b-chat-v1.0.q4-k-m__default.yaml`** (TinyLlama smoke). |
| **`loco config validate`** | All ok + usual stub-runtime warning. |
| **`loco serve …tinyllama…`** | Background **`running`** on port **8080**; **`GET /v1/models`** showed **`tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`**. |
| **`loco switch …qwen…`** | Returned to **`llamacpp__unsloth-qwen3.6-35b-a3b__ud-q4-k-xl__default`**; after ~25s **`/v1/models`** matched Qwen again (see readiness note above). |
