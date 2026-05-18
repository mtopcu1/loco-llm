#!/usr/bin/env bash
# Exit 0 when LLM_SERVE_HOST:LLM_SERVE_PORT accepts a TCP connection.
set -euo pipefail
python3 - <<'PY'
import os
import socket

host = os.environ.get("LLM_SERVE_HOST", "127.0.0.1")
port = int(os.environ["LLM_SERVE_PORT"])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect((host, port))
sock.close()
PY
