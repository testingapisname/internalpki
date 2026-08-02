from __future__ import annotations

import argparse
import datetime as dt
import time
from pathlib import Path

from .config import load_config
from .events import emit
from .health import HealthState, start_health_server
from .monitoring import collect
from .renewal import renew_target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Internal PKI renewal controller")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--force", action="store_true", help="Renew every configured target")
    parser.add_argument(
        "--target",
        action="append",
        help="Limit the cycle to this target ID; may be supplied more than once",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    targets = config.targets
    if args.target:
        requested = set(args.target)
        known = {target.target_id for target in targets}
        unknown = requested - known
        if unknown:
            raise SystemExit(f"Unknown target(s): {', '.join(sorted(unknown))}")
        targets = tuple(target for target in targets if target.target_id in requested)
    state = HealthState()
    server = start_health_server(config.health_host, config.health_port, state)
    emit("controller_started", targets=len(targets), interval=config.interval_seconds)
    try:
        while True:
            results: dict[str, str] = {}
            failures = 0
            for target in targets:
                try:
                    results[target.target_id] = renew_target(target, force=args.force)
                except Exception as error:  # keep other identities independent
                    failures += 1
                    results[target.target_id] = "error"
                    emit("renewal_failed", target=target.target_id, error=str(error))
            reports = []
            for target in targets:
                try:
                    reports.append(collect(target))
                except Exception as error:
                    failures += 1
                    reports.append(
                        {
                            "id": target.target_id,
                            "hostname": target.hostname,
                            "status": "ERROR",
                            "error": str(error),
                            "seconds_remaining": 0,
                            "connectivity": False,
                            "chain_valid": False,
                            "hostname_valid": False,
                            "deployed": False,
                        }
                    )
                    emit("monitoring_failed", target=target.target_id, error=str(error))
            checked_at = dt.datetime.now(dt.timezone.utc)
            unhealthy = any(report["status"] != "OK" for report in reports)
            state.update(
                {
                    "status": "degraded" if failures or unhealthy else "ok",
                    "checked_at": checked_at.isoformat(),
                    "targets": {report["id"]: report["status"] for report in reports},
                    "renewal_results": results,
                    "certificates": reports,
                    "last_cycle_timestamp": checked_at.timestamp(),
                }
            )
            emit("cycle_finished", failures=failures, results=results)
            if args.once:
                return 1 if failures else 0
            time.sleep(config.interval_seconds)
    finally:
        server.shutdown()
