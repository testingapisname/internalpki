# Renewal Incident 02: HTTP-01 Route Unavailable

## Scenario

App1 continued serving valid HTTPS, but an exercise-only Nginx configuration
returned HTTP 404 for every `/.well-known/acme-challenge/` request. A forced
controller renewal was attempted.

## Symptom

The ACME client retried validation for approximately 51 seconds and then failed:

```text
Using Webroot Mode HTTP challenge to validate app1.lab.local ... Error!
Unable to validate challenge: The server could not connect to validation target
```

The controller emitted `renewal_failed`, completed with one failure, and exited
with code 1.

## Root cause

The ACME client could write the challenge response, but Nginx deliberately
returned 404 instead of serving it. The CA could not validate HTTP control of
`app1.lab.local`, so the authorization never became valid and the order could
not be finalized.

## Diagnostic commands

```powershell
curl.exe --resolve app1.lab.local:8081:127.0.0.1 -i `
  http://app1.lab.local:8081/.well-known/acme-challenge/test-token

docker compose logs --since 5m --no-log-prefix step-ca nginx-app-1
```

## Correction

Recreate App1 using only the normal Compose model, then restart the controller:

```powershell
docker compose up -d --force-recreate nginx-app-1 certificate-controller
```

## Preventive controls

- Test the challenge route before creating an order.
- Keep ACME locations separate from application rewrite and authentication rules.
- Monitor authorization failures and Nginx challenge response codes.
- Bound external command execution time.
- Remove candidate files on every failed pre-deployment path.
- Preserve the active certificate until issuance and verification both succeed.

## Controller improvements produced by this exercise

- Configurable 120-second timeout for external `step` operations.
- Candidate cleanup for all issuance, verification, and fingerprint failures.
- ANSI color disabled so structured JSON error fields remain machine-friendly.
