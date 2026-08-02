#!/usr/bin/env python3
"""Safely renew and deploy an ACME certificate for a lab service."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Service:
    name: str
    hostname: str
    client: str
    nginx: str
    certificate_dir: Path
    csr_name: str
    certificate_name: str


SERVICES = {
    "app1": Service(
        name="app1",
        hostname="app1.lab.local",
        client="step-cli",
        nginx="nginx-app-1",
        certificate_dir=REPOSITORY_ROOT / "nginx" / "app1" / "certs",
        csr_name="app1.csr",
        certificate_name="app1-acme.crt",
    ),
    "app2": Service(
        name="app2",
        hostname="app2.lab.local",
        client="step-cli-app-2",
        nginx="nginx-app-2",
        certificate_dir=REPOSITORY_ROOT / "nginx" / "app2" / "certs",
        csr_name="app2.csr",
        certificate_name="app2-acme.crt",
    ),
}


def compose(*arguments: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run Docker Compose from the repository root."""
    command = ["docker", "compose", *arguments]
    print(f"+ {' '.join(command)}", flush=True)
    return subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        check=False,
        text=True,
        capture_output=capture,
    )


def require_success(result: subprocess.CompletedProcess[str], operation: str) -> None:
    if result.returncode == 0:
        return
    if result.stdout:
        print(result.stdout, file=sys.stderr, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    raise RuntimeError(f"{operation} failed with exit code {result.returncode}")


def fingerprint(service: Service, certificate: str) -> str:
    arguments = [
        "--profile",
        "tools",
        "run",
        "--rm",
        service.client,
        "certificate",
        "fingerprint",
        certificate,
    ]
    if certificate.startswith("https://"):
        arguments.extend(("--roots", "/roots/root_ca.crt"))
    result = compose(*arguments, capture=True)
    require_success(result, f"fingerprinting {certificate}")
    value = result.stdout.strip()
    if not value:
        raise RuntimeError(f"No fingerprint returned for {certificate}")
    return value.splitlines()[-1]


def restore_certificate(active: Path, backup: Path) -> None:
    """Restore the prior certificate after a failed validation or reload."""
    failed = active.with_suffix(active.suffix + ".failed")
    if failed.exists():
        failed.unlink()
    if active.exists():
        active.replace(failed)
    backup.replace(active)


def renew(service: Service, threshold: str, force: bool) -> None:
    active = service.certificate_dir / service.certificate_name
    next_name = f"{active.stem}.next{active.suffix}"
    next_path = service.certificate_dir / next_name

    if not active.exists():
        raise FileNotFoundError(f"Active certificate does not exist: {active}")

    print(f"Service: {service.name}")
    print(f"Hostname: {service.hostname}")
    print(f"Active certificate: {active.relative_to(REPOSITORY_ROOT)}")

    if not force:
        check = compose(
            "--profile",
            "tools",
            "run",
            "--rm",
            service.client,
            "certificate",
            "needs-renewal",
            f"/work/{service.certificate_name}",
            "--expires-in",
            threshold,
        )
        if check.returncode == 1:
            print(f"No renewal needed within threshold {threshold}.")
            return
        require_success(check, "checking certificate renewal status")
        print(f"Certificate is within the {threshold} renewal window.")
    else:
        print("Forced renewal requested; threshold check skipped.")

    if next_path.exists():
        next_path.unlink()

    old_fingerprint = fingerprint(service, f"/work/{service.certificate_name}")

    issue = compose(
        "--profile",
        "tools",
        "run",
        "--rm",
        service.client,
        "ca",
        "sign",
        f"/work/{service.csr_name}",
        f"/work/{next_name}",
        "--provisioner",
        "lab-acme",
        "--ca-url",
        "https://ca.lab.local:9000",
        "--root",
        "/roots/root_ca.crt",
        "--webroot",
        "/var/www/acme",
    )
    require_success(issue, "ACME issuance")

    verify = compose(
        "--profile",
        "tools",
        "run",
        "--rm",
        service.client,
        "certificate",
        "verify",
        f"/work/{next_name}",
        "--roots",
        "/roots/root_ca.crt",
    )
    require_success(verify, "new certificate verification")

    new_fingerprint = fingerprint(service, f"/work/{next_name}")
    if new_fingerprint == old_fingerprint:
        raise RuntimeError("Renewal returned the same certificate fingerprint")

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = active.with_name(f"{active.name}.{timestamp}.bak")
    active.replace(backup)
    next_path.replace(active)
    print(f"Preserved previous certificate: {backup.name}")

    config_test = compose("exec", service.nginx, "nginx", "-t")
    if config_test.returncode != 0:
        restore_certificate(active, backup)
        raise RuntimeError("Nginx configuration test failed; prior certificate restored")

    reload_result = compose("exec", service.nginx, "nginx", "-s", "reload")
    if reload_result.returncode != 0:
        restore_certificate(active, backup)
        compose("exec", service.nginx, "nginx", "-s", "reload")
        raise RuntimeError("Nginx reload failed; prior certificate restored")

    live_fingerprint = fingerprint(
        service,
        f"https://{service.hostname}",
    )
    if live_fingerprint != new_fingerprint:
        restore_certificate(active, backup)
        compose("exec", service.nginx, "nginx", "-s", "reload")
        raise RuntimeError(
            "Live endpoint did not present the renewed certificate; prior certificate restored"
        )

    print("Renewal and deployment succeeded.")
    print(f"Old fingerprint:  {old_fingerprint}")
    print(f"New fingerprint:  {new_fingerprint}")
    print(f"Live fingerprint: {live_fingerprint}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Renew and safely deploy a lab ACME certificate."
    )
    parser.add_argument("service", choices=sorted(SERVICES))
    parser.add_argument(
        "--threshold",
        default="4h",
        help="Renew when less than this duration remains (default: 4h).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip the threshold decision and perform a renewal now.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        renew(SERVICES[args.service], args.threshold, args.force)
    except (FileNotFoundError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
