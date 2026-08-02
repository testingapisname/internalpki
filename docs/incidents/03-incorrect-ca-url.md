# Renewal Incident 03: Incorrect CA URL

## Scenario

An exercise-only controller configuration pointed App1 at
`https://ca.lab.local:9443`. The healthy CA was listening on port 9000.

## Symptom

Renewal failed immediately during ACME client discovery:

```text
client GET https://ca.lab.local:9443/provisioners?limit=100 failed:
dial tcp 172.25.0.2:9443: connect: connection refused
```

The controller emitted `renewal_failed`, finished with one failure, and exited
with code 1.

## Root cause

The CA hostname and Docker DNS were healthy, but the client configuration used
the wrong TCP port. No process listened on port 9443.

## Diagnostic evidence

- DNS resolution succeeded and returned `172.25.0.2`.
- The connection failed specifically at TCP port 9443.
- The normal CA health endpoint on port 9000 remained healthy.
- No ACME order or HTTP-01 challenge was created.

## Correction

Restore the configured URL to:

```text
https://ca.lab.local:9000
```

The exercise used a separate TOML file, so recovery required only restarting
the normal controller:

```powershell
docker compose up -d certificate-controller
curl.exe http://localhost:8090/health
```

## Preventive controls

- Validate configuration at startup and test the ACME directory endpoint.
- Represent CA endpoints once and reference them rather than duplicating URLs.
- Include endpoint reachability in readiness checks.
- Keep known-bad exercise configuration separate from active configuration.
- Alert on connection-refused errors separately from DNS and TLS trust errors.
