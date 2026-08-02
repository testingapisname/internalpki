from __future__ import annotations

import os
import json
import subprocess
from pathlib import Path

from .models import CertificateTarget


class StepError(RuntimeError):
    pass


def run_step(target: CertificateTarget, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["STEPPATH"] = str(target.account_state)
    environment["NO_COLOR"] = "1"
    try:
        return subprocess.run(
            ["step", *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
            timeout=target.operation_timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise StepError(
            f"step operation timed out after {target.operation_timeout_seconds} seconds"
        ) from error


def require_success(result: subprocess.CompletedProcess[str], operation: str) -> str:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise StepError(f"{operation} failed ({result.returncode}): {detail}")
    return result.stdout.strip()


def needs_renewal(target: CertificateTarget) -> bool:
    result = run_step(
        target,
        "certificate",
        "needs-renewal",
        str(target.certificate),
        "--expires-in",
        target.renew_before,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    require_success(result, "renewal decision")
    return False


def fingerprint(target: CertificateTarget, value: str | Path) -> str:
    arguments = ["certificate", "fingerprint", str(value)]
    if str(value).startswith("https://"):
        arguments.extend(("--roots", str(target.root)))
    return require_success(run_step(target, *arguments), "certificate fingerprint").splitlines()[-1]


def issue(target: CertificateTarget, destination: Path) -> None:
    result = run_step(
        target,
        "ca",
        "sign",
        str(target.csr),
        str(destination),
        "--provisioner",
        target.provisioner,
        "--ca-url",
        target.ca_url,
        "--root",
        str(target.root),
        "--webroot",
        str(target.webroot),
    )
    require_success(result, "ACME issuance")


def verify(target: CertificateTarget, certificate: Path) -> None:
    require_success(
        run_step(
            target,
            "certificate",
            "verify",
            str(certificate),
            "--roots",
            str(target.root),
        ),
        "certificate verification",
    )


def inspect(target: CertificateTarget, certificate: Path) -> dict:
    output = require_success(
        run_step(
            target,
            "certificate",
            "inspect",
            "--format",
            "json",
            str(certificate),
        ),
        "certificate inspection",
    )
    return json.loads(output)
