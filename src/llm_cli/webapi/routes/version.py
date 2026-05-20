from fastapi import APIRouter

from llm_cli.core import dashboard as dash
from llm_cli.core.versions import current_cli_version

router = APIRouter()


@router.get("/version", tags=["meta"])
def version():
    try:
        record = dash.load_installed_record()
    except RuntimeError:
        record = None
    return {
        "cli_version": current_cli_version(),
        "dashboard_installed_cli_version": record.cli_version if record else None,
        "dashboard_installed_at": record.installed_at if record else None,
    }
