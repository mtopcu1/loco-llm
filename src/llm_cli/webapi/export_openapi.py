"""`python -m llm_cli.webapi.export_openapi` -> stdout."""
from __future__ import annotations

import json
import sys

from llm_cli.webapi.app import create_app


def main() -> int:
    app = create_app(allowed_hosts={"127.0.0.1:7878"})
    schema = app.openapi()
    # Strip server-specific noise that would create churn:
    schema.get("info", {}).pop("version", None)
    json.dump(schema, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
