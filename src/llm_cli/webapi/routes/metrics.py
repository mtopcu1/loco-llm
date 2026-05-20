from __future__ import annotations

from fastapi import APIRouter, Query

from llm_cli.core import metrics

router = APIRouter(tags=["metrics"])


@router.get("/configs/{config_id}/metrics/aggregate")
def metrics_aggregate(config_id: str, window: str = Query("7d")):
    return metrics.aggregate(config_id, window=window)


@router.get("/configs/{config_id}/metrics/sparkline")
def metrics_sparkline(
    config_id: str,
    bucket: str = Query("5m"),
    window: str = Query("24h"),
):
    return metrics.sparkline(config_id, bucket=bucket, window=window)
