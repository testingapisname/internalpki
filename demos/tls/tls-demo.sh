#!/bin/sh
set -eu

root=/trust/root_ca.crt

wait_for_http() {
  url="$1"
  name="$2"
  attempts=30

  while [ "$attempts" -gt 0 ]; do
    if curl --silent --show-error --fail "$url" >/dev/null; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 2
  done

  printf 'ERROR: timed out waiting for %s at %s\n' "$name" "$url" >&2
  exit 1
}

wait_for_https() {
  url="$1"
  name="$2"
  attempts=30

  while [ "$attempts" -gt 0 ]; do
    if curl --silent --show-error --fail --cacert "$root" "$url" >/dev/null; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 2
  done

  printf 'ERROR: timed out waiting for %s at %s\n' "$name" "$url" >&2
  exit 1
}

printf '\n=== 0. Wait for services to be reachable ===\n'
wait_for_https 'https://app1.lab.local/health' 'App1 HTTPS endpoint'
wait_for_https 'https://app2.lab.local/health' 'App2 HTTPS endpoint'
wait_for_http 'http://certificate-controller:8080/health' 'certificate-controller API'

printf '\n=== 1. Confirm the private CA is healthy ===\n'
curl --silent --show-error --fail \
  --cacert "$root" \
  https://ca.lab.local:9000/health
printf '\n'

printf '\n=== 2. Show why an ordinary client rejects the private CA ===\n'
if curl --silent --show-error --fail \
  https://app1.lab.local/health; then
  printf 'ERROR: connection unexpectedly trusted the private root\n' >&2
  exit 1
else
  printf 'EXPECTED: the client rejected the untrusted private root.\n'
fi

printf '\n=== 3. Trust the root and reach both HTTPS services ===\n'
curl --silent --show-error --fail \
  --cacert "$root" \
  https://app1.lab.local/health
printf '\n'
curl --silent --show-error --fail \
  --cacert "$root" \
  https://app2.lab.local/health
printf '\n'

printf '\n=== 4. Inspect App1 certificate identity and validity ===\n'
openssl s_client \
  -connect app1.lab.local:443 \
  -servername app1.lab.local \
  -CAfile "$root" \
  -verify_return_error </dev/null 2>/dev/null \
  | openssl x509 \
      -noout \
      -subject \
      -issuer \
      -dates \
      -ext subjectAltName

printf '\n=== 5. Prove that trust alone does not bypass hostname checks ===\n'
if curl --silent --show-error --fail \
  --cacert "$root" \
  --connect-to wrong.lab.local:443:app1.lab.local:443 \
  https://wrong.lab.local/health; then
  printf 'ERROR: wrong hostname unexpectedly passed verification\n' >&2
  exit 1
else
  printf 'EXPECTED: the trusted certificate was rejected for the wrong hostname.\n'
fi

printf '\n=== 6. Show certificate-controller health and inventory ===\n'
curl --silent --show-error --fail \
  http://certificate-controller:8080/health
printf '\n'
curl --silent --show-error --fail \
  http://certificate-controller:8080/certificates
printf '\n'

printf '\n=== TLS demo complete ===\n'
printf 'Trust chain, service identity, and automated monitoring all succeeded.\n'
