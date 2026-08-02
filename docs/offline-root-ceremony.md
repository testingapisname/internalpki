# Offline Root Extraction Ceremony

The root private key must not remain available to the online CA. This ceremony
moves its security boundary into a separate Docker volume while retaining the
public root certificate in the online chain.

The `offline-root-ceremony` service has no network and mounts online CA state
read-only. It is started only through the `ceremony` profile.

The lab also creates an encrypted backup outside the Docker volume under
`step-ca/offline-root-backup/`. That directory is ignored by Git. Because both
copies remain on the same physical computer, this models separation but is not
a production disaster-recovery backup.

The ceremony sequence is:

```text
Stop issuance
-> copy encrypted root key and public certificate
-> compare cryptographic hashes
-> verify the encrypted key can be decrypted
-> remove only the online root private key
-> restart the online CA
-> prove health and issuance without the root key
```

Never remove the online key until both destination copies have been verified.

## Completed ceremony evidence

The encrypted online key, offline-volume copy, and ignored host-backup copy all
had the same file digest:

```text
88a963974a73adba09ee5b4e5cba2ead490de954cae33a9d8af870ceb5c81794
```

The decrypted public-key fingerprint from both key copies matched the public
key embedded in the root certificate:

```text
SHA256:UkW1T496AJDqHngtGWIgGqbTmV+0J2dffzsdYcWcofo=
```

After extraction, the online volume reported:

```text
ROOT_KEY_ABSENT
INTERMEDIATE_KEY_PRESENT
PUBLIC_ROOT_CERTIFICATE_PRESENT
```

`step-ca` restarted with the same root fingerprint. A forced App2 ACME renewal
then changed the deployed leaf fingerprint from:

```text
33934db19fbdabe5bf93a81b5b6780bd3c40d8b1d21d4578d04c9031331167ea
```

to:

```text
0860286393e27cec49f4d9b9af479ef7291a8fe5a5bc04c4a6196754ba4fdeac
```

The live endpoint presented the replacement and the controller returned
healthy. This proves routine leaf issuance uses only the intermediate private
key.

## Current limitations

The offline volume and ignored backup are on the same physical Docker Desktop
host. This demonstrates access separation but not true offline media,
geographic redundancy, HSM protection, multi-person control, or disaster
recovery. A production ceremony should address each of those controls.
