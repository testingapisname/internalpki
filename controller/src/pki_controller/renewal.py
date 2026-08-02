from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

from .events import emit
from .models import CertificateTarget
from .step_client import fingerprint, issue, needs_renewal, verify


def _restore(active: Path, backup: Path) -> None:
    failed = active.with_suffix(active.suffix + ".failed")
    if failed.exists():
        failed.unlink()
    if active.exists():
        active.replace(failed)
    backup.replace(active)


def renew_target(target: CertificateTarget, force: bool = False) -> str:
    if not target.certificate.exists():
        raise FileNotFoundError(target.certificate)
    if not force and not needs_renewal(target):
        emit("renewal_not_needed", target=target.target_id, threshold=target.renew_before)
        return "not_needed"

    active = target.certificate
    candidate = active.with_name(f"{active.stem}.next{active.suffix}")
    if candidate.exists():
        candidate.unlink()

    old_fingerprint = fingerprint(target, active)
    emit("renewal_started", target=target.target_id, old_fingerprint=old_fingerprint)
    issue(target, candidate)
    verify(target, candidate)
    new_fingerprint = fingerprint(target, candidate)
    if new_fingerprint == old_fingerprint:
        candidate.unlink(missing_ok=True)
        raise RuntimeError("CA returned the existing certificate")

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = active.with_name(f"{active.name}.{timestamp}.bak")
    active.replace(backup)
    candidate.replace(active)
    emit(
        "certificate_deployed",
        target=target.target_id,
        old_fingerprint=old_fingerprint,
        new_fingerprint=new_fingerprint,
        backup=str(backup),
    )

    # Nginx owns its validation/reload. Poll until its live identity changes.
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            if fingerprint(target, target.verify_url) == new_fingerprint:
                emit("renewal_succeeded", target=target.target_id, fingerprint=new_fingerprint)
                return "renewed"
        except RuntimeError:
            pass
        time.sleep(2)

    _restore(active, backup)
    emit("renewal_rolled_back", target=target.target_id, reason="live verification timeout")
    raise RuntimeError("live endpoint did not deploy the new certificate within 45 seconds")

