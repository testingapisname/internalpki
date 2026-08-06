# Internal PKI Lab

## Quick demonstrations

Before running demos, initialize missing local secrets and start the core lab:

```text
python setup/create_secrets.py
docker compose up -d
```

Run the complete Nginx TLS and monitoring demonstration with:

```text
docker compose --profile tools build tls-demo
docker compose --profile tools run --rm tls-demo
```

The demo intentionally shows an untrusted-root failure and a hostname-mismatch
failure before validating both managed HTTPS services and the certificate
controller.

## Rebuildable setup

Cross-platform setup utilities live under `setup/`. Create all missing local
secret files with:

```text
python setup/create_secrets.py
```

The command skips existing secrets and never overwrites them. See
`setup/README.md` for setup phases and credential-rotation cautions.

A local, containerized learning lab for exploring the complete TLS certificate
lifecycle. The lab progresses from building a CA hierarchy and issuing a
certificate manually to ACME automation, renewal, incident exercises, and
certificate monitoring.

The environment remains local: it does not require a public domain or expose
services to the internet.

## Lab guides

- [Initial setup and manual PKI walkthrough](docs/initial-setup.md)
- [ACME HTTP-01 challenge setup](docs/acme-http01-setup.md)
- [Certificate controller architecture and operation](controller/README.md)
- [Offline root extraction ceremony](docs/offline-root-ceremony.md)
- [Operational runbook](docs/operational-runbook.md)
- [Code signing lab](docs/code-signing-lab.md)

## Prerequisites

- Windows 10 or later
- PowerShell
- Docker Desktop using Linux containers
- Docker Compose v2

The Smallstep and OpenSSL utilities will run inside containers, so they do not
need to be installed directly on Windows.

## Repository layout

```text
internal-pki-lab/
|-- compose.yaml       # Containers, network, and persistent volumes
|-- step-ca/           # CA configuration maintained by the lab
|-- nginx/
|   |-- app1/          # First HTTPS service
|   `-- app2/          # Second independently managed HTTPS service
|-- client/            # Certificate and ACME client configuration
|-- scripts/           # Repeatable PowerShell operations
`-- monitoring/        # Certificate health checker
```

Empty directories contain `.gitkeep` placeholder files so Git can track the
layout before later phases add configuration.

## Phase 1: project foundation

Phase 1 establishes:

- an isolated Docker bridge network named `internal-pki-lab`;
- persistent volumes for the CA and both application identities;
- separation between CA, service, client, automation, and monitoring files;
- safeguards against accidentally committing private keys or generated state.

Validate the Compose model without starting containers:

```powershell
docker compose config
```

The current Compose file intentionally contains no services. Networks and
volumes are declared now and will be used when the CA and applications are
introduced in later phases.

## Secret-handling rule

Generated private keys, passwords, ACME account data, and CA state must not be
committed. The repository's `.gitignore` provides defense in depth, but it is
not a substitute for checking staged changes before every commit:

```powershell
git status
git diff --cached
```

Public certificates are normally safe to distribute. Private keys and password
files are secret. Later phases will examine each artifact and this distinction
in detail.

## Progress

- [x] Phase 1: repository, storage declarations, network, and secret safeguards
- [x] Phase 2: root and intermediate CA hierarchy
- [x] Phase 3: start `step-ca` and validate explicit root trust
- [x] Phase 4: manually generate App1's key, CSR, and leaf certificate
- [x] Phase 5: serve App1 over HTTPS and reproduce common TLS failures
- [x] Phase 6: record the certificate inventory
- [x] Phase 7: enable and inspect the ACME provisioner
- [x] Phase 8: obtain and deploy App1's certificate through ACME
- [x] Phase 9: add an independently managed App2 service
- [x] Phase 10: automate renewal and Nginx reload with the controller
- [x] Security milestone: remove the root private key from the online CA
- [ ] Phases 11-14: incident and failure exercises
- [x] Phases 15-16: controller monitoring, structured output, and metrics
- [x] Phase 17: operational runbook
- [ ] Phase 18: final demonstration

Detailed commands, explanations, observed results, and troubleshooting notes
are recorded in the [initial setup walkthrough](docs/initial-setup.md) and the
[ACME HTTP-01 guide](docs/acme-http01-setup.md).
