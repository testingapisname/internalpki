# Internal PKI Operational Runbook

This runbook describes routine operation of the local Internal PKI environment.
Run commands from the repository root:

```text
Z:\InternalPKI01
```

## 1. System architecture

```text
Offline root storage
`-- Root private key (not mounted by online services)

Online Docker network: internal-pki-lab
|-- step-ca
|   `-- Intermediate private key signs leaf certificates
|-- nginx-app-1
|-- nginx-app-2
`-- certificate-controller
    |-- ACME renewal scheduler
    |-- Certificate inventory
    |-- TLS validation
    |-- Health API
    `-- Prometheus metrics
```

The public root certificate remains online so clients can validate chains. The
root private key is isolated in `internal-pki-lab-offline-root-data` and an
ignored encrypted backup.

## 2. Important locations

| Purpose | Location |
|---|---|
| Compose model | `compose.yaml` |
| Controller configuration | `controller/controller.toml` |
| App1 active certificate | `nginx/app1/certs/app1-acme.crt` |
| App1 private key | `nginx/app1/certs/app1.key` |
| App2 active certificate | `nginx/app2/certs/app2-acme.crt` |
| App2 private key | `nginx/app2/certs/app2.key` |
| Public root certificate | `step-ca/root_ca.crt` |
| Offline-root backup | `step-ca/offline-root-backup/` |
| Incident records | `docs/incidents/` |
| Controller source | `controller/src/pki_controller/` |

Private keys, passwords, generated certificates, account state, and backup
material must not be committed.

## 3. Normal startup

Start the normal environment:

```powershell
docker compose up -d
```

This does not start services assigned only to `tools`, `exercises`, or
`ceremony` profiles.

Check status:

```powershell
docker compose ps
```

Expected normal services:

```text
step-ca
nginx-app-1
nginx-app-2
certificate-controller
```

The CA should become `healthy`. The controller should be running on local port
8090.

## 4. Normal shutdown

Stop and remove containers and the network while preserving named volumes:

```powershell
docker compose down
```

Do not add `--volumes` during normal operation. The following command destroys
persistent CA, ACME-account, controller, and challenge state:

```text
docker compose down --volumes
```

Use it only when intentionally destroying and rebuilding the lab.

## 5. Service endpoints

| Service | Host URL |
|---|---|
| CA | `https://localhost:9000` |
| App1 HTTP | `http://localhost:8081` |
| App1 HTTPS | `https://localhost:8443` |
| App2 HTTP | `http://localhost:8082` |
| App2 HTTPS | `https://localhost:8445` |
| Controller | `http://localhost:8090` |

All published ports bind to `127.0.0.1` and are not intentionally exposed to
the LAN.

## 6. Verify CA health

Container state:

```powershell
docker compose ps step-ca
docker compose logs --tail 50 --no-log-prefix step-ca
```

TLS health using the explicit trust anchor:

```powershell
curl.exe `
  --ssl-no-revoke `
  --cacert .\step-ca\root_ca.crt `
  https://localhost:9000/health
```

Expected:

```json
{"status":"ok"}
```

`--ssl-no-revoke` addresses the lab's lack of Schannel-compatible revocation
status infrastructure. It does not disable chain or hostname validation.

## 7. Verify application HTTPS

App1:

```powershell
curl.exe `
  --ssl-no-revoke `
  --cacert .\step-ca\root_ca.crt `
  --resolve app1.lab.local:8443:127.0.0.1 `
  https://app1.lab.local:8443/health
```

App2:

```powershell
curl.exe `
  --ssl-no-revoke `
  --cacert .\step-ca\root_ca.crt `
  --resolve app2.lab.local:8445:127.0.0.1 `
  https://app2.lab.local:8445/health
```

## 8. Controller health and inventory

Overall health:

```powershell
curl.exe http://localhost:8090/health
```

Authoritative current certificate inventory:

```powershell
curl.exe http://localhost:8090/certificates
```

Prometheus metrics:

```powershell
curl.exe http://localhost:8090/metrics
```

Controller logs:

```powershell
docker compose logs --tail 100 --no-log-prefix certificate-controller
```

Normal status is `OK`. Investigate `WARNING`, `CRITICAL`, `EXPIRED`, or `ERROR`.

## 9. Renewal policy

The controller runs immediately at startup and every 900 seconds afterward.
Each eight-hour certificate has these lab thresholds:

```text
Renewal decision  Fewer than 4 hours remain
WARNING           Fewer than 4 hours remain
CRITICAL          Fewer than 1 hour remains
EXPIRED           Validity has ended
```

Checking every 15 minutes does not issue a certificate every 15 minutes.

## 10. Run one controller cycle

Evaluate every configured target without starting another persistent scheduler:

```powershell
docker compose run --rm `
  certificate-controller `
  --config /config/controller.toml `
  --once
```

Limit evaluation to one identity:

```powershell
docker compose run --rm `
  certificate-controller `
  --config /config/controller.toml `
  --once `
  --target app1
```

## 11. Force renewal

Use forced renewal only for testing, recovery, or an approved operational need.

App1:

```powershell
docker compose run --rm `
  certificate-controller `
  --config /config/controller.toml `
  --once `
  --force `
  --target app1
```

Replace `app1` with `app2` for App2.

A successful transaction must emit:

```text
renewal_started
certificate_deployed
renewal_succeeded
cycle_finished with failures=0
```

The new fingerprint must match the certificate served over the network.

## 12. Renewal and deployment safety

The controller performs:

```text
Issue to candidate path
-> verify chain
-> compare fingerprints
-> preserve timestamped backup
-> atomically replace active file
-> wait for service-local Nginx reload
-> verify live fingerprint
-> roll back if live deployment does not complete
```

Nginx containers monitor their own certificate files. On a change, each watcher
runs `nginx -t` and reloads locally. The controller does not have Docker-socket
access.

## 13. Inspect a certificate

App1:

```powershell
docker compose --profile tools run --rm `
  step-cli `
  certificate inspect /work/app1-acme.crt
```

App2:

```powershell
docker compose --profile tools run --rm `
  step-cli-app-2 `
  certificate inspect /work/app2-acme.crt
```

Check subject, SANs, issuer, serial, validity, key algorithm, provisioner, and
fingerprint.

## 14. Verify certificate chains

App1:

```powershell
docker compose --profile tools run --rm `
  step-cli `
  certificate verify /work/app1-acme.crt `
  --roots /roots/root_ca.crt

$LASTEXITCODE
```

Exit code 0 with no output means success.

Use `step-cli-app-2` and `/work/app2-acme.crt` for App2.

## 15. Verify a live fingerprint

```powershell
docker compose --profile tools run --rm `
  step-cli `
  certificate fingerprint https://app1.lab.local `
  --roots /roots/root_ca.crt
```

Compare the result with `/certificates` and the managed file fingerprint.

## 16. Inspect the ACME directory

```powershell
curl.exe `
  --ssl-no-revoke `
  --cacert .\step-ca\root_ca.crt `
  --resolve ca.lab.local:9000:127.0.0.1 `
  https://ca.lab.local:9000/acme/lab-acme/directory
```

The response should advertise `newNonce`, `newAccount`, `newOrder`,
`revokeCert`, and `keyChange`.

## 17. Diagnose failed HTTP-01 challenges

Verify the challenge path through the intended application:

```powershell
curl.exe `
  --resolve app1.lab.local:8081:127.0.0.1 `
  http://app1.lab.local:8081/.well-known/acme-challenge/test-token
```

Review both sides:

```powershell
docker compose logs --since 10m --no-log-prefix step-ca nginx-app-1
```

Check:

- The controller can write the webroot.
- Nginx mounts the same webroot read-only.
- The URL returns HTTP 200 with exact content.
- Docker DNS resolves the application alias.
- Nginx application rules do not intercept the ACME location.

## 18. Diagnose trust and chain failures

Common distinctions:

| Symptom | Likely cause |
|---|---|
| `UNTRUSTED_ROOT` | Client lacks the lab root |
| `PARTIAL_CHAIN` | Server omitted the intermediate |
| Hostname mismatch | Requested name absent from SAN |
| `key values mismatch` | Certificate and private key differ |
| Connection refused | No listener or wrong port |

Never use `--insecure` as a corrective action. Supply the correct trust anchor,
chain, hostname, or key material.

## 19. CA outage response

Existing HTTPS services continue operating while their deployed certificates
remain valid. New issuance and renewal fail.

Check:

```powershell
docker compose ps -a step-ca
docker compose logs --tail 100 step-ca certificate-controller
```

Recover:

```powershell
docker compose up -d step-ca certificate-controller
curl.exe http://localhost:8090/health
```

Do not replace active certificates with partial candidates during an outage.

## 20. Offline-root operation

The normal online environment must report:

```text
Root private key: absent
Intermediate private key: present
Public root certificate: present
```

The offline-root volume must never be mounted into `step-ca` or the controller.
Use the `ceremony` profile only for controlled root operations:

```powershell
docker compose --profile ceremony run --rm offline-root-ceremony --help
```

See `docs/offline-root-ceremony.md` before any root operation. Do not restore
the root key to online storage for routine leaf issuance.

## 21. Logs

```powershell
# All normal services
docker compose logs --since 15m

# CA issuance and ACME protocol
docker compose logs --since 15m step-ca

# Renewal and monitoring decisions
docker compose logs --since 15m certificate-controller

# HTTP-01 and reload activity
docker compose logs --since 15m nginx-app-1 nginx-app-2
```

Controller logs are structured JSON. Preserve relevant events with timestamps,
target IDs, old and new fingerprints, and errors.

## 22. Backup

Backups contain highly sensitive CA and account material. Store them encrypted,
restrict access, and test restoration.

Before backing up online CA state:

```powershell
docker compose stop certificate-controller step-ca
```

Back up these logical components separately:

- Online CA volume `internal-pki-lab-step-ca-data`
- Offline root volume `internal-pki-lab-offline-root-data`
- ACME account volumes for App1 and App2
- Controller configuration and source from Git
- Ignored service private keys and certificates
- Ignored offline-root backup

Restart normal services after the snapshot:

```powershell
docker compose up -d step-ca certificate-controller
```

A same-host Docker volume copy is not sufficient disaster recovery. Maintain an
encrypted copy on separate media or a separate secured system.

## 23. Restore principles

Do not overwrite the active CA volume as the first restore attempt.

1. Restore into a newly named volume or isolated environment.
2. Verify expected files and permissions.
3. Confirm the root private key is absent from the restored online volume.
4. Start an isolated CA with no production network exposure.
5. Verify root fingerprint and CA health.
6. Test chain validation and a controlled issuance.
7. Switch the active configuration only after validation.
8. Record the restore timeline and evidence.

Restoring the offline root is a separate ceremony and must not be combined with
routine online-CA recovery unless root signing is actually required.

## 24. Incident evidence template

Record every failure or security event using:

```text
Incident ID
Start and end time in UTC
Affected identity
Symptom
Relevant logs
Old serial and fingerprint
Root cause
Diagnostic commands
Correction
Post-recovery validation
Preventive control
```

Existing examples are stored in `docs/incidents/`.

## 25. Escalation conditions

Stop routine automation and investigate when:

- The root private key appears in online storage.
- A managed and live fingerprint differ unexpectedly.
- Chain or hostname validation fails.
- Renewal repeatedly fails inside the critical window.
- An unknown ACME account or certificate appears.
- A private key may have been copied or exposed.
- The CA root fingerprint changes unexpectedly.
- Backup restoration cannot reproduce the expected identity.

Do not erase failed artifacts or logs until evidence is preserved.

## 26. Current limitations

This remains a lab and early controller MVP. It does not yet provide:

- HSM or KMS-backed intermediate keys
- Durable controller database and distributed locks
- Authenticated monitoring API
- High-availability CA or controller
- Production revocation-status infrastructure
- Automated private-key rotation
- Complete revocation workflow
- Tested cross-host encrypted backup restoration
- Multi-user authorization or approval workflows

Treat these as required design work before production deployment.
