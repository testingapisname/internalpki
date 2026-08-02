from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class HealthState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: dict[str, Any] = {"status": "starting", "targets": {}}

    def update(self, value: dict[str, Any]) -> None:
        with self._lock:
            self._value = value

    def read(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._value)


def start_health_server(host: str, port: int, state: HealthState) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/health":
                self.send_error(404)
                return
            body = json.dumps(state.read()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

