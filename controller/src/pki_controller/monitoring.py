from __future__ import annotations

import datetime as dt
import hashlib
import socket
import ssl
from typing import Any
from urllib.parse import urlparse

from .models import CertificateTarget
from .step_client import inspect, verify


def classify_status(
    seconds_remaining: float,
    connectivity: bool,
    chain_valid: bool,
    hostname_valid: bool,
    warning_before: int,
    critical_before: int,
) -> str:
    if not connectivity or not chain_valid or not hostname_valid:
        return "ERROR"
    if seconds_remaining <= 0:
        return "EXPIRED"
    if seconds_remaining < critical_before:
        return "CRITICAL"
    if seconds_remaining < warning_before:
        return "WARNING"
    return "OK"


def _tls_checks(target: CertificateTarget) -> tuple[bool, bool, bool, str | None, str | None]:
    parsed = urlparse(target.verify_url)
    host = parsed.hostname or target.hostname
    port = parsed.port or 443
    connectivity = False
    chain_valid = False
    hostname_valid = False
    live_fingerprint: str | None = None
    error: str | None = None

    try:
        with socket.create_connection((host, port), timeout=5):
            connectivity = True
    except OSError as exc:
        return False, False, False, None, str(exc)

    chain_context = ssl.create_default_context(cafile=str(target.root))
    chain_context.check_hostname = False
    try:
        with socket.create_connection((host, port), timeout=5) as raw:
            with chain_context.wrap_socket(raw, server_hostname=host) as tls:
                chain_valid = True
                der = tls.getpeercert(binary_form=True)
                live_fingerprint = hashlib.sha256(der).hexdigest()
    except (OSError, ssl.SSLError) as exc:
        error = str(exc)

    hostname_context = ssl.create_default_context(cafile=str(target.root))
    hostname_context.check_hostname = True
    try:
        with socket.create_connection((host, port), timeout=5) as raw:
            with hostname_context.wrap_socket(raw, server_hostname=target.hostname):
                hostname_valid = True
    except (OSError, ssl.SSLError) as exc:
        error = str(exc)

    return connectivity, chain_valid, hostname_valid, live_fingerprint, error


def collect(target: CertificateTarget) -> dict[str, Any]:
    metadata = inspect(target, target.certificate)
    local_chain_valid = True
    try:
        verify(target, target.certificate)
    except Exception:
        local_chain_valid = False

    end = dt.datetime.fromisoformat(metadata["validity"]["end"].replace("Z", "+00:00"))
    seconds_remaining = (end - dt.datetime.now(dt.timezone.utc)).total_seconds()
    connectivity, remote_chain, hostname_valid, live_fingerprint, error = _tls_checks(target)
    chain_valid = local_chain_valid and remote_chain
    fingerprint = metadata["fingerprint_sha256"]
    deployed = live_fingerprint == fingerprint
    if not deployed and error is None:
        error = "live certificate fingerprint differs from managed certificate"

    status = classify_status(
        seconds_remaining,
        connectivity,
        chain_valid,
        hostname_valid and deployed,
        target.warning_before_seconds,
        target.critical_before_seconds,
    )
    return {
        "id": target.target_id,
        "hostname": target.hostname,
        "subject": metadata["subject_dn"],
        "issuer": metadata["issuer_dn"],
        "serial_number": metadata["serial_number"],
        "not_before": metadata["validity"]["start"],
        "not_after": metadata["validity"]["end"],
        "seconds_remaining": round(seconds_remaining, 3),
        "hours_remaining": round(seconds_remaining / 3600, 3),
        "key_algorithm": metadata["subject_key_info"]["key_algorithm"]["name"],
        "dns_names": metadata.get("extensions", {}).get("subject_alt_name", {}).get("dns_names", []),
        "provisioner": metadata.get("extensions", {}).get("step_provisioner", {}),
        "fingerprint_sha256": fingerprint,
        "live_fingerprint_sha256": live_fingerprint,
        "connectivity": connectivity,
        "chain_valid": chain_valid,
        "hostname_valid": hostname_valid,
        "deployed": deployed,
        "status": status,
        "error": error,
    }


def prometheus(reports: list[dict[str, Any]], last_cycle: float) -> str:
    lines = [
        "# HELP pki_controller_last_cycle_timestamp_seconds Last completed monitoring cycle.",
        "# TYPE pki_controller_last_cycle_timestamp_seconds gauge",
        f"pki_controller_last_cycle_timestamp_seconds {last_cycle}",
        "# HELP pki_certificate_seconds_remaining Seconds until certificate expiration.",
        "# TYPE pki_certificate_seconds_remaining gauge",
        "# HELP pki_certificate_connectivity TLS endpoint TCP connectivity (1 or 0).",
        "# TYPE pki_certificate_connectivity gauge",
        "# HELP pki_certificate_chain_valid Certificate chain validation result (1 or 0).",
        "# TYPE pki_certificate_chain_valid gauge",
        "# HELP pki_certificate_hostname_valid Certificate hostname validation result (1 or 0).",
        "# TYPE pki_certificate_hostname_valid gauge",
        "# HELP pki_certificate_deployed Managed certificate is live (1 or 0).",
        "# TYPE pki_certificate_deployed gauge",
    ]
    for report in reports:
        labels = f'id="{report["id"]}",hostname="{report["hostname"]}"'
        lines.extend(
            [
                f'pki_certificate_seconds_remaining{{{labels}}} {report["seconds_remaining"]}',
                f'pki_certificate_connectivity{{{labels}}} {int(report["connectivity"])}',
                f'pki_certificate_chain_valid{{{labels}}} {int(report["chain_valid"])}',
                f'pki_certificate_hostname_valid{{{labels}}} {int(report["hostname_valid"])}',
                f'pki_certificate_deployed{{{labels}}} {int(report["deployed"])}',
            ]
        )
    return "\n".join(lines) + "\n"
