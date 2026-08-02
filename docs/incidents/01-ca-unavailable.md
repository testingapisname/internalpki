# Renewal Incident 01: CA Unavailable

## Scenario

The certificate controller and `step-ca` were stopped. A one-time forced App1
renewal was then executed with Compose dependency startup disabled.

## Symptom

The controller started the renewal transaction but failed during ACME issuance:

```text
client GET https://ca.lab.local:9000/provisioners?limit=100 failed:
dial tcp: lookup ca.lab.local on 127.0.0.11:53: no such host
```

The controller emitted `renewal_failed`, completed the cycle with one failure,
and exited with code 1.

## Relevant evidence

```json
{"event":"renewal_started","target":"app1","old_fingerprint":"d38a618ca221f28934d3670bee9f7ed2b32520a6e8d688e7997861ac1ec7f3dc"}
{"event":"renewal_failed","target":"app1","error":"ACME issuance failed ... no such host"}
{"event":"cycle_finished","failures":1,"results":{"app1":"error"}}
```

## Root cause

The CA container was stopped. Its `ca.lab.local` network alias was therefore
not registered in Docker's embedded DNS, so the client could not resolve or
contact the ACME service.

## Diagnostic commands

```powershell
docker compose ps -a step-ca certificate-controller
docker compose logs --tail 50 step-ca certificate-controller
docker compose run --rm --no-deps certificate-controller `
  --config /config/controller.toml --once --force --target app1
```

The `--no-deps` option was essential to the exercise because normal Compose
startup would have started the CA dependency automatically.

## Safety verification

- Candidate certificate path did not exist after failure.
- App1 continued returning a healthy HTTPS response.
- Live certificate fingerprint remained:

```text
d38a618ca221f28934d3670bee9f7ed2b32520a6e8d688e7997861ac1ec7f3dc
```

The controller never reached deployment because issuance failed. Existing TLS
services do not require the CA to remain online; they require it only for new
issuance and renewal.

## Correction

```powershell
docker compose up -d step-ca certificate-controller
curl.exe http://localhost:8090/health
```

After recovery, the controller reported both targets as `not_needed`.

## Preventive controls

- Monitor CA health and renewal-controller health independently.
- Alert on `renewal_failed` events and nonzero cycle failure counts.
- Begin renewal early enough to allow multiple retries before expiration.
- Use retry backoff with jitter instead of rapid repeated issuance attempts.
- Preserve the active certificate until a replacement is issued and verified.
- Run redundant CA instances and durable database storage for production use.
