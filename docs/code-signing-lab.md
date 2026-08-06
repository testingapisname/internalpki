# Code Signing Lab

## Goal

Build a purpose-specific Authenticode hierarchy and demonstrate publisher
trust, artifact integrity, tamper detection, expiration, and trusted
timestamping. All compilation, signing, and verification operations run in
Linux containers so the host only needs Docker and Git.

The `artifact-signer` image contains MinGW-w64 and `osslsigncode`. It can build
a real Windows PE executable and apply or verify its Authenticode signature
without using a Windows certificate store or host signing utility.

## One-command demonstration

After the publisher certificate and private key have been created, rebuild the
tooling image and run the complete integrity demonstration:

```text
docker compose --profile tools build artifact-signer
docker compose --profile tools run --rm artifact-signer code-signing-demo
```

The demonstration builds an unsigned PE executable, confirms it has no
signature, signs and validates it, modifies a copy, and requires signature
verification of the modified copy to fail. Password input is read directly
from the mounted Docker secret.

## Planned hierarchy

```text
Lab Root CA (offline private key)
|-- Lab Root CA Intermediate CA       TLS issuance
`-- Lab Code Signing Intermediate CA  Publisher issuance
    `-- Lab Software Publisher        Code-signing leaf
```

The code-signing intermediate is separate from the TLS intermediate so policy,
key access, audit events, revocation, and compromise impact can be managed
independently.

The publisher leaf will be constrained to:

```text
Basic Constraints: CA:FALSE
Key Usage: Digital Signature
Extended Key Usage: Code Signing (1.3.6.1.5.5.7.3.3)
```

It must not contain TLS Server Authentication or Client Authentication EKUs.

The `code-signing` JWK provisioner enforces this profile using
`code-signing/templates/publisher.tpl`. The initialization provisioner,
`codesign-admin`, remains separate and is not used for routine publisher
certificate issuance.

## Timestamp Authority policy

The Timestamp Authority uses a separate key and provisioner. Its certificate
template is `code-signing/templates/timestamp-authority.tpl` and permits only:

```text
Basic Constraints: CA:FALSE
Key Usage: Digital Signature
Extended Key Usage: Time Stamping (1.3.6.1.5.5.7.3.8), critical
```

The critical Extended Key Usage is encoded explicitly as extension OID
`2.5.29.37`. The template value is the DER encoding of a sequence containing
only the RFC 3161 Time Stamping purpose OID.

The `timestamp-cli` tools service has access only to the public root, the TSA
workspace, the timestamp issuance credential, and the TSA key password. It has
no access to publisher or CA private keys.

The TSA CSR uses `code-signing/templates/timestamp-request.tpl`, which requests
only the subject and public key. Unlike the default TLS-oriented CSR template,
it does not convert the human-readable TSA subject into a DNS SAN.

## RFC 3161 responder

The `timestamp-authority` service exposes an RFC 3161 endpoint at
`http://timestamp.lab.local:8080/timestamp` inside the Compose network and at
`http://localhost:9010/timestamp` on the host. It uses OpenSSL to sign timestamp
queries, includes the TSA certificate chain, and persists monotonically
increasing response serial numbers in a dedicated Docker volume.

The first implementation is intentionally single-threaded. This serializes
access to OpenSSL's serial file and avoids issuing duplicate serial numbers.
Production evolution should add authenticated signing requests, rate limiting,
high-availability serial allocation, immutable audit storage, and stronger key
protection.

Before Authenticode integration, generate and verify a raw RFC 3161 exchange:

```text
openssl ts -query -data artifact -sha256 -cert -out request.tsq
curl -H 'Content-Type: application/timestamp-query' \
  --data-binary @request.tsq http://timestamp.lab.local:8080/timestamp \
  --output response.tsr
openssl ts -verify -queryfile request.tsq -in response.tsr \
  -CAfile /trust/root_ca.crt
```

The request contains a message imprint (a hash), not the artifact itself. The
response binds that imprint to the TSA's independently asserted time and
signature.

## Ceremony rule

The root private key is mounted only into the network-isolated
`offline-root-ceremony` service. After it signs the code-signing intermediate,
the root private key must be absent from the online code-signing CA volume.
