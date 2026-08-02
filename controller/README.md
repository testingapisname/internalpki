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
`http://localhost:8090/health`. The production scheduler evaluates every
configured target immediately at startup and every 900 seconds thereafter.

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

This is an early MVP. Before production use it still needs durable database
state, distributed locking, authentication, secret/KMS backends, concurrency
limits, richer retry policy, and integration testing under failure.
