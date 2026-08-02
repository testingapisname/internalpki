from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .monitoring import prometheus


class HealthState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: dict[str, Any] = {
            "status": "starting",
            "checked_at": None,
            "targets": {},
            "renewal_results": {},
            "certificates": [],
            "last_cycle_timestamp": 0.0,
        }

    def update(self, value: dict[str, Any]) -> None:
        with self._lock:
            self._value = value

    def read(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._value)


def start_health_server(host: str, port: int, state: HealthState) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            snapshot = state.read()
            if self.path == "/health":
                payload = {
                    key: snapshot[key]
                    for key in ("status", "checked_at", "targets", "renewal_results")
                }
                body = json.dumps(payload).encode("utf-8")
                content_type = "application/json"
            elif self.path == "/certificates":
                body = json.dumps({"certificates": snapshot["certificates"]}).encode("utf-8")
                content_type = "application/json"
            elif self.path == "/metrics":
                body = prometheus(
                    snapshot["certificates"], snapshot["last_cycle_timestamp"]
                ).encode("utf-8")
                content_type = "text/plain; version=0.0.4"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
