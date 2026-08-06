# Lab Setup

This directory contains cross-platform, idempotent setup utilities. Run them
from a Python environment on any host with Docker Compose available.

## Create local secrets

Create every missing secret:

```text
python setup/create_secrets.py
```

Create only the timestamping secrets:

```text
python setup/create_secrets.py --group timestamping
```

Available groups are `tls`, `code-signing`, and `timestamping`. Existing files
are skipped and are never overwritten. To rotate a credential, follow the
relevant runbook; deleting and replacing a password file alone does not
re-encrypt keys that use the old password.

Secret files are stored under `step-ca/secrets/`, which is ignored by Git.
They are local runtime inputs and must not be committed.

## Configure timestamping issuance

After the code-signing CA has been initialized, add its constrained
timestamping provisioner with:

```text
python setup/configure_timestamping.py
```

The operation is idempotent. It creates a missing `timestamping` provisioner or
updates the policy and lifetime settings of an existing one. During initial
creation, the new provisioner password is streamed to the CA process over
standard input and is not copied into or permanently mounted in the CA
container.

## Rebuild roadmap

The setup workflow will grow into explicit phases:

1. Create local secrets.
2. Validate Docker and Compose prerequisites.
3. Initialize or restore the offline root.
4. Initialize the TLS and code-signing intermediates.
5. Configure restricted provisioners.
6. Issue initial service, publisher, and timestamping identities.
7. Start services and run smoke tests.

Destructive reset and restore operations will remain separate from normal,
idempotent setup so rerunning setup cannot erase an existing PKI.
