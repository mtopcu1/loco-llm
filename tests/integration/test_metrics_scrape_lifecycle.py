import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from llm_cli.core import metrics
from llm_cli.webapi.streams import EventHub

PROM_BODY = """# TYPE vllm:tokens_per_second gauge
vllm:tokens_per_second{phase="decode"} 99.0
"""


class StubHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(PROM_BODY.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), StubHandler)
    port = server.server_port
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    yield ("127.0.0.1", port)
    server.shutdown()


@pytest.mark.asyncio
async def test_scrape_task_writes_snapshot_and_publishes(stub_server, tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "_metrics_dir", lambda: tmp_path)
    host, port = stub_server
    manifest_metrics = {
        "endpoint": "/metrics",
        "fields": {
            "tps_decode": {"promql_metric": 'vllm:tokens_per_second{phase="decode"}'},
        },
    }
    hub = EventHub()
    task = metrics.MetricsScrapeTask(
        config_id="cfg",
        runtime_id="vllm",
        manifest_metrics=manifest_metrics,
        host=host,
        port=port,
        hub=hub,
        interval_seconds=0.1,
    )
    task.start()

    sub = hub.subscribe()
    received = []

    async def consume():
        async for ev in sub.events(timeout=2.0):
            received.append(ev)
            if len(received) >= 2:
                break

    await asyncio.wait_for(consume(), timeout=3.0)
    await task.stop()

    assert len(received) >= 2
    assert received[0]["tps_decode"] == 99.0
    snaps = list(metrics.read_snapshots("cfg"))
    assert len(snaps) >= 2
