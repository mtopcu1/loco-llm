from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from llm_cli.core import doctor as doctor_core

router = APIRouter()


@router.get("/doctor", tags=["doctor"])
def doctor():
    return {
        "scopes": {
            scope: [asdict(result) for result in doctor_core.run_scope(scope)]
            for scope in ("default", "runtime", "dashboard")
        }
    }
