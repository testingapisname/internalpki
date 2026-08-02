from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CertificateTarget:
    target_id: str
    hostname: str
    csr: Path
    certificate: Path
    account_state: Path
    webroot: Path
    ca_url: str
    root: Path
    provisioner: str
    renew_before: str
    verify_url: str
    operation_timeout_seconds: int


@dataclass(frozen=True)
class ControllerConfig:
    interval_seconds: int
    health_host: str
    health_port: int
    targets: tuple[CertificateTarget, ...]
