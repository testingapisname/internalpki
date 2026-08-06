"""Minimal single-threaded RFC 3161 HTTP timestamp responder for the lab."""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


LISTEN_ADDRESS = "0.0.0.0"
LISTEN_PORT = 8080
MAX_REQUEST_BYTES = 1024 * 1024
CERTIFICATE_BUNDLE = Path("/pki/lab-timestamp-authority.crt")
RUNTIME_DIRECTORY = Path("/tmp/tsa-runtime")
SERIAL_FILE = Path("/state/tsa.serial")


def event(name: str, **fields: object) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": name,
        **fields,
    }
    print(json.dumps(record, separators=(",", ":")), flush=True)


def prepare_certificates() -> None:
    pem = CERTIFICATE_BUNDLE.read_text(encoding="ascii")
    marker = "-----END CERTIFICATE-----"
    blocks = [part.strip() + "\n" + marker + "\n" for part in pem.split(marker) if part.strip()]
    if len(blocks) < 2:
        raise RuntimeError("TSA bundle must contain a leaf and intermediate certificate")

    RUNTIME_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIRECTORY / "tsa-leaf.crt").write_text(blocks[0], encoding="ascii")
    (RUNTIME_DIRECTORY / "tsa-chain.crt").write_text(
        "".join(blocks[1:]), encoding="ascii"
    )

    if not SERIAL_FILE.exists():
        SERIAL_FILE.write_text("01\n", encoding="ascii")


class TimestampHandler(BaseHTTPRequestHandler):
    server_version = "InternalPKITSA/0.1"

    def log_message(self, format: str, *args: object) -> None:
        event("http_access", client=self.client_address[0], message=format % args)

    def send_body(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_body(404, "text/plain; charset=utf-8", b"not found\n")
            return
        body = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_body(200, "application/json", body)

    def do_POST(self) -> None:
        if self.path != "/timestamp":
            self.send_body(404, "text/plain; charset=utf-8", b"not found\n")
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type != "application/timestamp-query":
            self.send_body(415, "text/plain; charset=utf-8", b"expected timestamp query\n")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self.send_body(413, "text/plain; charset=utf-8", b"invalid request size\n")
            return

        request_body = self.rfile.read(length)
        with tempfile.TemporaryDirectory(prefix="tsa-request-") as temporary:
            query = Path(temporary) / "request.tsq"
            response = Path(temporary) / "response.tsr"
            query.write_bytes(request_body)
            command = [
                "openssl",
                "ts",
                "-reply",
                "-config",
                "/app/tsa.conf",
                "-section",
                "tsa_config",
                "-queryfile",
                str(query),
                "-out",
                str(response),
                "-passin",
                "file:/run/secrets/timestamp_key_password",
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode != 0:
                event("timestamp_failed", error=completed.stderr.strip())
                self.send_body(500, "text/plain; charset=utf-8", b"timestamp failed\n")
                return

            response_body = response.read_bytes()

        event("timestamp_issued", response_bytes=len(response_body))
        self.send_body(200, "application/timestamp-reply", response_body)


def main() -> None:
    prepare_certificates()
    event("timestamp_authority_started", address=LISTEN_ADDRESS, port=LISTEN_PORT)
    HTTPServer((LISTEN_ADDRESS, LISTEN_PORT), TimestampHandler).serve_forever()


if __name__ == "__main__":
    main()
