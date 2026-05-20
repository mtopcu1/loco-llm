from __future__ import annotations

from fastapi import APIRouter

from llm_cli.core import recommendations as rec_module

router = APIRouter()


@router.get("/recommendations", tags=["recommendations"])
def recommendations(runtime_id: str, model_id: str | None = None):
    recs = rec_module.compute(runtime_id=runtime_id, model_id=model_id)
    return [r.as_dict() for r in recs]
