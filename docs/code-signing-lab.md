# Code Signing Lab

## Goal

Build a purpose-specific Authenticode hierarchy and demonstrate publisher
trust, artifact integrity, tamper detection, expiration, and trusted
timestamping. All compilation, signing, and verification operations run in
Linux containers so the host only needs Docker and Git.

The `artifact-signer` image contains MinGW-w64 and `osslsigncode`. It can build
a real Windows PE executable and apply or verify its Authenticode signature
without using a Windows certificate store or host signing utility.

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

## Ceremony rule

The root private key is mounted only into the network-isolated
`offline-root-ceremony` service. After it signs the code-signing intermediate,
the root private key must be absent from the online code-signing CA volume.
