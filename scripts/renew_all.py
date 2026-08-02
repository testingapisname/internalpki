#!/usr/bin/env python3
"""Run scheduled renewal checks for every lab HTTPS service."""

from __future__ import annotations

import contextlib
import datetime as dt
import sys
from pathlib import Path
from typing import TextIO

from renew_certificate import REPOSITORY_ROOT, SERVICES, renew


class Tee:
    """Write Python output to both the current stream and a log file."""

    def __init__(self, stream: TextIO, log: TextIO) -> None:
        self.stream = stream
        self.log = log

    def write(self, value: str) -> int:
        self.stream.write(value)
        self.log.write(value)
        self.flush()
        return len(value)

    def flush(self) -> None:
        self.stream.flush()
        self.log.flush()


def main() -> int:
    output_directory = REPOSITORY_ROOT / "monitoring" / "output"
    output_directory.mkdir(parents=True, exist_ok=True)
    log_path = output_directory / "renewal.log"

    failures = 0
    with log_path.open("a", encoding="utf-8") as log:
        with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(
            Tee(sys.stderr, log)
        ):
            started = dt.datetime.now(dt.timezone.utc).isoformat()
            print(f"\n=== Renewal check started {started} ===")
            for name in ("app1", "app2"):
                try:
                    renew(SERVICES[name], threshold="4h", force=False)
                except (FileNotFoundError, RuntimeError) as error:
                    failures += 1
                    print(f"ERROR [{name}]: {error}", file=sys.stderr)
            finished = dt.datetime.now(dt.timezone.utc).isoformat()
            print(
                f"=== Renewal check finished {finished}; failures={failures} ==="
            )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
