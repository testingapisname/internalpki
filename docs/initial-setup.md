# Initial Setup and Manual PKI Walkthrough

This guide records the lab work completed through manual HTTPS configuration.
It explains not only which commands were run, but what each artifact means and
why the observed success and failure modes occurred.

> Never commit or paste private keys, CA passwords, or provisioner passwords.
> The values shown here are public certificate metadata from this lab.

## 1. Architecture established so far

```text
Windows host
|
`-- Docker Compose network: internal-pki-lab
    |-- step-ca
    |   |-- Lab Root CA
    |   `-- Lab Intermediate CA
    |
    `-- nginx-app-1
        `-- app1.lab.local leaf certificate
```

The repository separates CA configuration, Nginx services, client material,
scripts, and monitoring. Generated CA state, passwords, private keys, issued
certificates, exercise evidence, and monitoring output are excluded by
`.gitignore`.

Validate the Compose model at any time:

```powershell
docker compose config --quiet
```

Successful validation produces no output and exits with status zero.

## 2. Containerized tooling

The lab uses the Smallstep tools from a container rather than requiring a
native Windows installation:

```powershell
docker pull smallstep/step-ca:latest

docker run --rm `
  --entrypoint step `
  smallstep/step-ca:latest `
  version
```

The initialized lab uses Smallstep CA 0.30.2. The Compose image is pinned to
that version for reproducibility.

`--entrypoint step` replaces the image's normal CA-server entrypoint with the
administrative `step` CLI.

## 3. Persistent storage and secret handling

The CA uses the named volume `internal-pki-lab-step-ca-data`, mounted at
`/home/step`. A named volume survives container deletion and ordinary
`docker compose down` operations.

The CA key-encryption password is read from:

```text
step-ca/secrets/ca-password.txt
```

This file is plaintext because the CA must read it during unattended startup.
It is ignored by Git. Confirm that without printing the secret:

```powershell
Test-Path .\step-ca\secrets\ca-password.txt
git check-ignore -v .\step-ca\secrets\ca-password.txt
```

Do not use `docker compose down --volumes` unless intentionally destroying the
lab CA. The `--volumes` option deletes persistent CA state.

## 4. Initializing the CA hierarchy

The hierarchy was initialized once in the persistent volume:

```powershell
docker compose run --rm `
  --entrypoint step `
  step-ca `
  ca init `
  --deployment-type standalone `
  --name "Lab Root CA" `
  --dns ca.lab.local `
  --dns step-ca `
  --dns localhost `
  --dns 127.0.0.1 `
  --address ":9000" `
  --provisioner "lab-admin" `
  --password-file /run/secrets/ca_password `
  --provisioner-password-file /run/secrets/ca_password
```

Do not rerun initialization against an already initialized volume.

The command created:

```text
/home/step/
|-- certs/
|   |-- root_ca.crt
|   `-- intermediate_ca.crt
|-- secrets/
|   |-- root_ca_key
|   `-- intermediate_ca_key
|-- config/
|   |-- ca.json
|   `-- defaults.json
`-- db/
```

The lab's public root fingerprint is:

```text
c1e273b61e5a35a78103af8372f2bc22a3119ddff5b2e5f7632714408b981b6b
```

### CA roles

```text
Root certificate          Explicit client trust anchor
`-- Intermediate          Signs routine leaf certificates
    `-- Leaf              Identifies a service such as app1.lab.local
```

The root certificate is self-signed: its subject and issuer are the same. The
intermediate certificate's issuer is the root.

The root contains `CA:TRUE, pathlen:1`, allowing one subordinate CA level. The
intermediate contains `CA:TRUE, pathlen:0`, allowing it to issue leaves but not
another subordinate CA.

The intermediate Authority Key Identifier matches the root Subject Key
Identifier. Actual signature verification was performed with:

```powershell
docker compose run --rm `
  --entrypoint step `
  step-ca `
  certificate verify /home/step/certs/intermediate_ca.crt `
  --roots /home/step/certs/root_ca.crt
```

Silent success means the intermediate signature validated against the root.

### Why the root key should be offline

The online CA needs the intermediate private key for routine leaf issuance. It
does not need the root private key. Protecting the root offline limits damage
if the online intermediate is compromised: the protected root can create a
replacement intermediate without distributing a new trust anchor to every
client.

This lab initially stores both encrypted keys in one volume for accessibility.
A production design should separate the root key and use controlled signing
ceremonies, potentially backed by an HSM.

An HSM keeps a private key non-exportable and performs signing internally. It
does not eliminate the need for authorization, policy, audit logging, backup,
or high availability. An online service with permission to invoke an HSM key
may still misuse that key if the service is compromised.

## 5. Starting and validating the CA

Start the online CA:

```powershell
docker compose up -d step-ca
docker compose ps
docker compose logs --tail 30 --no-log-prefix step-ca
```

Healthy startup includes:

```text
The primary server URL is https://ca.lab.local:9000
Serving HTTPS on :9000
```

The Compose command must explicitly invoke `step-ca` before the configuration
path. Omitting it makes the image try to execute `ca.json`, which produces a
misleading `Permission denied` error.

Exporting the public root does not expose a secret:

```powershell
docker cp `
  internal-pki-step-ca:/home/step/certs/root_ca.crt `
  .\step-ca\root_ca.crt
```

An untrusted request fails:

```powershell
curl.exe https://localhost:9000/health
```

On Windows Schannel, the result was `SEC_E_UNTRUSTED_ROOT`.

An explicitly trusted request succeeds:

```powershell
curl.exe `
  --ssl-no-revoke `
  --cacert .\step-ca\root_ca.crt `
  https://localhost:9000/health
```

Expected response:

```json
{"status":"ok"}
```

The lab CA does not expose the revocation information expected by Schannel, so
Windows may report `CERT_TRUST_REVOCATION_STATUS_UNKNOWN`. `--ssl-no-revoke`
disables only that revocation lookup; it still checks trust, signatures,
validity, and hostname. It is not equivalent to `--insecure`.

Test the intended hostname without modifying the Windows hosts file:

```powershell
curl.exe `
  --ssl-no-revoke `
  --cacert .\step-ca\root_ca.crt `
  --resolve ca.lab.local:9000:127.0.0.1 `
  https://ca.lab.local:9000/health
```

A certificate may be correctly signed, unexpired, and valid for its hostname
but remain rejected until a client explicitly trusts its root.

## 6. Generating the App1 identity

Create an ignored working directory:

```powershell
New-Item -ItemType Directory -Force .\nginx\app1\certs
git check-ignore -v .\nginx\app1\certs
```

Generate an ECDSA P-256 key pair:

```powershell
docker compose run --rm `
  --entrypoint step `
  --volume "${PWD}\nginx\app1\certs:/work" `
  step-ca `
  crypto keypair `
  /work/app1.pub `
  /work/app1.key `
  --kty EC `
  --curve P-256 `
  --no-password `
  --insecure
```

Artifacts:

```text
app1.key   Unencrypted private key; secret
app1.pub   Public key; distributable
```

Nginx must load its key unattended. Therefore, the server key is unencrypted,
and protection shifts to file permissions, restricted mounts, container
isolation, monitoring, and incident response.

## 7. Creating and inspecting the CSR

Use the existing key rather than generating a replacement:

```powershell
docker compose run --rm `
  --entrypoint step `
  --volume "${PWD}\nginx\app1\certs:/work" `
  step-ca `
  certificate create `
  --csr `
  --key /work/app1.key `
  --san app1.lab.local `
  app1.lab.local `
  /work/app1.csr
```

Inspect it:

```powershell
docker compose run --rm `
  --entrypoint step `
  --volume "${PWD}\nginx\app1\certs:/work" `
  step-ca `
  certificate inspect /work/app1.csr
```

The CSR contains the subject, requested SAN, public key, and a signature made
with App1's private key. It does not contain the private key, issuer, validity
period, or certificate serial number.

The CSR signature proves possession of the private key. It does not establish
authorization to use the requested hostname; that decision belongs to the CA.
Modern clients validate DNS identities against SANs rather than relying on the
Common Name (`CN`).

## 8. Manually issuing App1's certificate

From a one-off container created from the `step-ca` service, use the Compose
service name `step-ca` as the CA URL:

```powershell
docker compose run --rm `
  --entrypoint step `
  --volume "${PWD}\nginx\app1\certs:/work" `
  step-ca `
  ca sign `
  /work/app1.csr `
  /work/app1.crt `
  --ca-url https://step-ca:9000 `
  --root /home/step/certs/root_ca.crt `
  --provisioner lab-admin `
  --provisioner-password-file /run/secrets/ca_password `
  --not-after 24h
```

Do not use `https://ca.lab.local:9000` from this particular one-off container.
It inherits the service hostname `ca.lab.local` and may resolve that name to
itself, causing `connection refused`. The Compose DNS name `step-ca` reaches the
running server and is covered by its certificate SAN.

The JWK provisioner authorizes the request by creating a short-lived token. The
intermediate private key performs the certificate signature. Authorization
and certificate signing are distinct roles.

The resulting certificate has:

```text
Subject:       CN=app1.lab.local
SAN:           app1.lab.local
Issuer:        Lab Root CA Intermediate CA
Algorithm:     ECDSA P-256 with ECDSA-SHA256 signature
Serial:        7e253491d1aa3f5670899d6940b3aa75
Not Before:    2026-08-01 15:18:52 UTC
Not After:     2026-08-02 15:19:52 UTC
Provisioner:   lab-admin (JWK)
```

The one-minute validity backdating allowance helps tolerate minor clock skew.

`app1.crt` contains two PEM blocks:

```text
Leaf certificate
Intermediate certificate
```

The root is not included because a TLS client should already possess its trust
anchor. Verify the bundle with:

```powershell
docker compose run --rm `
  --entrypoint step `
  --volume "${PWD}\nginx\app1\certs:/work" `
  step-ca `
  certificate verify /work/app1.crt `
  --roots /home/step/certs/root_ca.crt
```

## 9. Key versus certificate fingerprints

The private and public key fingerprint commands returned the same result:

```text
SHA256:GH3dQoOtqk7YnvFlsCfNxjW0zFkKhuvJJlEzB92RAsU=
```

This is expected because `step crypto key fingerprint` fingerprints the public
component. For a private key, it first derives or extracts that public part.

This does not mean the certificate has the same fingerprint:

```text
Key fingerprint         Hash of normalized public-key material
Certificate fingerprint Hash of the complete encoded X.509 certificate
```

The certificate hash also covers its subject, issuer, serial, validity,
extensions, public key, and CA signature. Fingerprints may also be displayed in
Base64 or hexadecimal, so output encoding must be considered when comparing
values.

## 10. Serving App1 with Nginx

The healthy Nginx service uses:

```nginx
ssl_certificate     /etc/nginx/tls/app1.crt;
ssl_certificate_key /etc/nginx/tls/app1.key;
ssl_protocols       TLSv1.2 TLSv1.3;
```

The certificate directory is mounted read-only. Start the service:

```powershell
docker compose up -d nginx-app-1
docker compose ps
docker compose logs --tail 30 --no-log-prefix nginx-app-1
```

The host ports are:

```text
127.0.0.1:8081 -> HTTP port 80
127.0.0.1:8443 -> HTTPS port 443
```

Test trusted HTTPS:

```powershell
curl.exe `
  --ssl-no-revoke `
  --cacert .\step-ca\root_ca.crt `
  --resolve app1.lab.local:8443:127.0.0.1 `
  https://app1.lab.local:8443/health
```

Expected response:

```json
{"status":"ok","service":"app1.lab.local"}
```

This success verifies connectivity, TLS negotiation, chain signatures, root
trust, validity, hostname, the certificate/key relationship, and the HTTP
response.

## 11. Failure exercises completed

### TCP connection refused

Symptom:

```text
curl: (7) Couldn't connect to server
```

Cause: App1 had not been started. TLS validation cannot occur until TCP
connectivity succeeds.

Diagnostics:

```powershell
docker compose ps -a
docker compose logs --tail 50 --no-log-prefix nginx-app-1
Test-NetConnection 127.0.0.1 -Port 8443
```

### Untrusted root

Requesting App1 without `--cacert` produced `SEC_E_UNTRUSTED_ROOT`. The chain
was valid, but Windows had not chosen the lab root as a trust anchor.

### Hostname mismatch

The correct chain was presented while requesting `wrong.lab.local`:

```powershell
curl.exe `
  --ssl-no-revoke `
  --cacert .\step-ca\root_ca.crt `
  --resolve wrong.lab.local:8443:127.0.0.1 `
  https://wrong.lab.local:8443/health
```

The request failed because the certificate SAN contains only
`app1.lab.local`. Trust and identity are independent validation dimensions.

### Incomplete chain

A leaf-only file was extracted from the full bundle and served by the exercise
endpoint on port 8444. It produced:

```text
CERT_TRUST_IS_PARTIAL_CHAIN
```

The client possessed the root but could not build `leaf -> intermediate ->
root` because the server omitted the intermediate.

Windows may sometimes cache an intermediate received previously. A clean
client should be used if an intentionally incomplete server unexpectedly
validates.

### Private-key mismatch

An unrelated key produced a different public-key fingerprint. The isolated
Nginx configuration test paired that key with `app1.crt`:

```powershell
docker compose --profile exercises run --rm nginx-app-1-key-mismatch
```

Nginx correctly refused to start:

```text
SSL_CTX_use_PrivateKey(...) failed
x509 certificate routines::key values mismatch
```

Trust, hostname, and chain errors are normally detected by clients. A
certificate/private-key mismatch is detected by the server while loading its
TLS configuration.

## 12. Current operational commands

```powershell
# Start normal services
docker compose up -d step-ca nginx-app-1

# Show status
docker compose ps

# Show logs
docker compose logs --tail 50 step-ca nginx-app-1

# Stop containers while preserving CA state
docker compose down

# Start the intentionally broken chain endpoint
docker compose --profile exercises up -d nginx-app-1-incomplete-chain

# Test the intentionally mismatched key configuration
docker compose --profile exercises run --rm nginx-app-1-key-mismatch
```

## 13. Artifact classification

| Artifact | Secret? | Purpose |
|---|---:|---|
| Root certificate | No | Client trust anchor |
| Intermediate certificate | No | Verifies leaf signatures |
| Root private key | Yes | Signs intermediate CAs |
| Intermediate private key | Yes | Signs routine leaf certificates |
| App1 private key | Yes | Proves App1's server identity |
| App1 public key | No | Public half of App1's key pair |
| App1 CSR | No | Requests certification of App1's public key and identity |
| App1 certificate chain | No | Presents App1's certified identity and issuer chain |
| CA/provisioner password | Yes | Decrypts protected signing or authorization keys |

## 14. Next step

The next phase creates a certificate inventory recording service ownership,
DNS names, issuer, serial, validity, algorithm, paths, renewal method, and
fingerprint. After that, the lab introduces an ACME provisioner and replaces
manual enrollment with automated issuance and renewal.
