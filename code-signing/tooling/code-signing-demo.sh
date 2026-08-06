#!/bin/sh
set -eu

unsigned=/artifacts/demo-unsigned.exe
signed=/artifacts/demo-signed.exe
tampered=/artifacts/demo-tampered.exe

rm -f "$unsigned" "$signed" "$tampered"

printf '\n=== 1. Build a real Windows PE executable in Linux ===\n'
x86_64-w64-mingw32-gcc \
  -O2 -Wall -Wextra \
  -o "$unsigned" \
  /source/hello.c
file "$unsigned"
sha256sum "$unsigned"

printf '\n=== 2. Confirm the original has no Authenticode signature ===\n'
if osslsigncode verify -in "$unsigned"; then
  printf 'ERROR: unsigned artifact unexpectedly passed verification\n' >&2
  exit 1
else
  printf 'EXPECTED: unsigned artifact was rejected.\n'
fi

printf '\n=== 3. Sign it with the certified publisher key ===\n'
osslsigncode sign \
  -certs /publisher/lab-software-publisher.crt \
  -key /publisher/lab-software-publisher.key \
  -readpass /run/secrets/publisher_key_password \
  -h sha256 \
  -n "Internal PKI Lab Demo" \
  -in "$unsigned" \
  -out "$signed"
sha256sum "$signed"

printf '\n=== 4. Verify integrity, publisher identity, and trust chain ===\n'
osslsigncode verify \
  -CAfile /trust/root_ca.crt \
  -in "$signed"

printf '\n=== 5. Tamper with a copy of the signed executable ===\n'
cp "$signed" "$tampered"
dd if=/dev/zero of="$tampered" bs=16 count=1 seek=256 conv=notrunc 2>/dev/null
sha256sum "$signed" "$tampered"

printf '\n=== 6. Prove the embedded signature no longer matches ===\n'
if osslsigncode verify -CAfile /trust/root_ca.crt -in "$tampered"; then
  printf 'ERROR: tampered artifact unexpectedly passed verification\n' >&2
  exit 1
else
  printf 'EXPECTED: tampered artifact was rejected.\n'
fi

printf '\n=== Demo complete ===\n'
printf 'Unsigned, signed, and tampered artifacts are in code-signing/artifacts/.\n'
