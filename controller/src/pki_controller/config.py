from __future__ import annotations

import tomllib
from pathlib import Path

from .models import CertificateTarget, ControllerConfig


def load_config(path: Path) -> ControllerConfig:
    with path.open("rb") as stream:
        raw = tomllib.load(stream)

    controller = raw.get("controller", {})
    targets = tuple(
        CertificateTarget(
            target_id=item["id"],
            hostname=item["hostname"],
            csr=Path(item["csr"]),
            certificate=Path(item["certificate"]),
            account_state=Path(item["account_state"]),
            webroot=Path(item["webroot"]),
            ca_url=item["ca_url"],
            root=Path(item["root"]),
            provisioner=item.get("provisioner", "lab-acme"),
            renew_before=item.get("renew_before", "4h"),
            verify_url=item["verify_url"],
            operation_timeout_seconds=int(item.get("operation_timeout_seconds", 120)),
        )
        for item in raw.get("certificate", [])
    )
    if not targets:
        raise ValueError("Configuration must define at least one [[certificate]]")
    ids = [target.target_id for target in targets]
    if len(ids) != len(set(ids)):
        raise ValueError("Certificate target IDs must be unique")

    return ControllerConfig(
        interval_seconds=int(controller.get("interval_seconds", 900)),
        health_host=controller.get("health_host", "0.0.0.0"),
        health_port=int(controller.get("health_port", 8080)),
        targets=targets,
    )
