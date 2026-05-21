# Dashboard workflow catalog

Add an entry when the user defines a repeatable workflow. Copy steps verbatim from their message.

## pull-model

**Steps (example):**

1. Open http://127.0.0.1:7878/
2. Go to Models
3. Click **Pull from HF**
4. Paste Hugging Face file URL (`…/blob/main/….gguf`)
5. Click **Pull**
6. Watch job panel until complete
7. Confirm model row appears in table

**Notes:** Large downloads may take minutes; job logs may be sparse early.

---

## full-runtime-serve (2026-05-21)

**Steps:**

1. Clear all runtime installations (dashboard Runtimes → Uninstall + purge).
2. Install **llamacpp** and **vllm** from dashboard (note: no Ollama runtime in repo).
3. Pull small models: GGUF file URL + safetensors repo URL (&lt;2GB).
4. Create 3 configs: 2× llamacpp (GGUF), 1× vllm.
5. Instance: serve each config separately (background mode).
6. Try starting a second config while one is running.
7. Switch between configs; note duration.
8. `ps` / stop: check for orphan `hf download` or server processes.

**Report:** [docs/superpowers/reports/2026-05-21-full-runtime-serve-workflow.md](../../../docs/superpowers/reports/2026-05-21-full-runtime-serve-workflow.md)

---

<!-- Add more workflows below as the user defines them. -->
