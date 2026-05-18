# Add a per-runtime recommendation

`llm advisor` and `llm config setup` read suggestions from [`src/llm_cli/core/recommendations.py`](../src/llm_cli/core/recommendations.py). **v1** implements one branch for **`llamacpp`** on **`ctx`** and **`n_gpu_layers`**.

Extend `recommend(...)` with a new runtime id branch. Return **`None`** when prerequisites are missing (no GPU signal, unknown weights size, unsupported param key); callers fall back to schema defaults quietly.

## Skeleton

```python
def recommend(runtime_id, param_key, *, model, specs):
    if runtime_id == "llamacpp":
        return _llamacpp(param_key, model=model, specs=specs)
    if runtime_id == "vllm":
        return _vllm(param_key, model=model, specs=specs)
    return None


def _vllm(param_key, *, model, specs):
    if model is None or specs is None or not specs.gpus:
        return None
    if param_key == "gpu-memory-utilization":
        return Recommendation(value="0.9", reason="example: leave KV headroom (estimate)")
    return None
```

## Label estimates

Every `Recommendation.reason` should read as an **estimate**. Wrong guesses are worse than silence — prefer **`None`** when unsure.

## Tests

Add cases in [`tests/unit/test_recommendations.py`](../tests/unit/test_recommendations.py): happy paths for representative hardware, **`None`** when preconditions fail, and **`None`** for unknown param keys.
