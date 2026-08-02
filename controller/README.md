# Certificate Controller

The controller is a single scheduler and worker process for multiple
certificate identities. It reads `controller.toml`, evaluates each certificate
every 15 minutes, renews identities inside their policy window, deploys through
atomic file replacement, and verifies the live endpoint.

It deliberately has no Docker socket, CA password, root private key, or
intermediate private key. Per-service ACME account state, certificate folders,
and HTTP-01 webroots remain separate mounts.

Nginx reload is service-local: a watcher in each Nginx container notices a
certificate change, validates configuration with `nginx -t`, and reloads.

Run one non-renewing evaluation cycle:

```powershell
docker compose run --rm certificate-controller --config /config/controller.toml --once
```

Force one target for an end-to-end deployment test:

```powershell
docker compose run --rm certificate-controller --config /config/controller.toml --once --force --target app1
```

Start the scheduled controller:

```powershell
docker compose up -d certificate-controller
curl.exe http://localhost:8090/health
docker compose logs -f certificate-controller
```

The controller health endpoint is bound only to the local host at
`http://localhost:8090`. The production scheduler evaluates every
configured target immediately at startup and every 900 seconds thereafter.

Endpoints:

| Path | Purpose |
|---|---|
| `/health` | Overall state, per-target severity, and renewal decisions |
| `/certificates` | Authoritative live certificate inventory and validation results |
| `/metrics` | Prometheus-compatible gauges |

Example healthy state:

```json
{
  "status": "ok",
  "targets": {
    "app1": "not_needed",
    "app2": "not_needed"
  }
}
```

Structured JSON events are written to standard output for collection through
the container logging driver.

Certificate status thresholds are configured per target. The lab uses:

```text
OK        At least 4 hours remain and all checks pass
WARNING   Less than 4 hours remain
CRITICAL  Less than 1 hour remains
EXPIRED   Validity has ended
ERROR     Connectivity, chain, hostname, or deployment validation failed
```

Monitoring independently checks the managed file and live endpoint. A service
is considered deployed only when the SHA-256 fingerprint served over TLS
matches the controller's current certificate file.

Prometheus metrics include:

```text
pki_controller_last_cycle_timestamp_seconds
pki_certificate_seconds_remaining
pki_certificate_connectivity
pki_certificate_chain_valid
pki_certificate_hostname_valid
pki_certificate_deployed
```

The `/certificates` endpoint supersedes the static CSV as the authoritative
current-state inventory. The CSV remains useful as historical lab evidence.

This is an early MVP. Before production use it still needs durable database
state, distributed locking, authentication, secret/KMS backends, concurrency
limits, richer retry policy, and integration testing under failure.
