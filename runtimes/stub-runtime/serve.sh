#!/usr/bin/env bash
# Toy TCP listener for smoke tests and `loco serve` integration against stub-runtime.
# Responds with a line of "hello" to each connection. Honors SIGINT/SIGTERM.
set -euo pipefail
exec python3 - <<'PY'
import os
import signal
import socket

host = os.environ.get("LLM_SERVE_HOST", "127.0.0.1")
port = int(os.environ["LLM_SERVE_PORT"])

stop = False


def _stop(_signum=None, _frame=None):
    global stop
    stop = True


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((host, port))
sock.listen(8)
sock.settimeout(0.5)
while not stop:
    try:
        conn, _addr = sock.accept()
    except socket.timeout:
        continue
    except OSError:
        break
    try:
        conn.sendall(b"hello\n")
    finally:
        conn.close()
sock.close()
PY
