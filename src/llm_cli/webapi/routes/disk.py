from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from llm_cli.core import disk

router = APIRouter()


@router.get("/disk", tags=["disk"])
def get_disk():
    return asdict(disk.scan())
