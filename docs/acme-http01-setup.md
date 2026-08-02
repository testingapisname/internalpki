# ACME HTTP-01 Challenge Setup

This guide explains how the lab prepares and validates the HTTP-01 challenge
path used to obtain certificates automatically from `step-ca`.

It covers challenge plumbing only. Successfully retrieving the test token
proves that the path is ready, but it does not issue a certificate.

## Purpose of HTTP-01

Before issuing a certificate for `app1.lab.local`, the CA needs evidence that
the requester controls that HTTP service. During an HTTP-01 challenge, the ACME
client places a CA-selected response at a well-known URL:

```text
http://app1.lab.local/.well-known/acme-challenge/<token>
```

The CA retrieves that URL. If the response matches the expected value, the
authorization can become valid and certificate issuance may proceed.

HTTP-01 proves control of the HTTP endpoint. It does not prove legal ownership
of a name, ownership of every service using a name, or possession of an
existing TLS private key.

## Lab data flow

```text
step-cli
   |
   | writes challenge token
   v
Docker volume: app1-acme-webroot
   |
   | mounted read-only
   v
nginx-app-1
   |
   | serves token over HTTP port 80
   v
step-ca retrieves and validates the response
```

The ACME client needs write access because it creates temporary challenge
files. Nginx needs only read access because it serves those files and should
not modify them.

## Compose resources

The named volume is declared in `compose.yaml`:

```yaml
volumes:
  app1-acme-webroot:
    name: internal-pki-lab-app1-acme-webroot
```

The client mounts it read/write:

```yaml
step-cli:
  volumes:
    - app1-acme-webroot:/var/www/acme
```

Nginx mounts the same volume read-only:

```yaml
nginx-app-1:
  volumes:
    - app1-acme-webroot:/var/www/acme:ro
```

The `:ro` suffix enforces the intended access direction at the container mount
boundary.

## Nginx challenge route

App1's Nginx configuration contains:

```nginx
location ^~ /.well-known/acme-challenge/ {
    root /var/www/acme;
    default_type text/plain;
    try_files $uri =404;
}
```

For a request such as:

```text
/.well-known/acme-challenge/test-token
```

Nginx reads:

```text
/var/www/acme/.well-known/acme-challenge/test-token
```

`try_files $uri =404` ensures that Nginx returns the requested challenge file
when it exists and a clear HTTP 404 response when it does not.

## Recreating App1 with the new mount

After changing Compose mounts or Nginx configuration, validate the model and
recreate the container:

```powershell
docker compose config --quiet
docker compose up -d --force-recreate nginx-app-1
docker compose ps
```

`--force-recreate` replaces the container so it receives the new volume mount.
It does not delete the named volume.

## Diagnosing the initial permission failure

The first attempt to create the challenge directory returned:

```text
mkdir: can't create directory '/var/www/acme/.well-known/': Permission denied
```

Docker initialized the new volume directory as owned by Linux `root`. The
Smallstep image runs as an unprivileged user, so it could mount and see the
volume but could not create content in it.

This is a filesystem ownership failure. It is not an Nginx routing, ACME
protocol, DNS, or CA trust failure.

## Identifying the client UID and GID

The client container's effective identity was checked with:

```powershell
docker compose --profile tools run --rm `
  --entrypoint id `
  step-cli
```

Result:

```text
uid=1000(step) gid=1000(step) groups=1000(step)
```

Although Docker Desktop runs on Windows, these are Linux containers. Files in
Docker named volumes therefore use Linux numeric user and group ownership.

Running the service as a non-root user reduces the impact of a compromised
client process.

## Initializing volume ownership

A one-time container ran as root to prepare the volume:

```powershell
docker compose --profile tools run --rm `
  --user 0:0 `
  --entrypoint sh `
  step-cli `
  -c 'mkdir -p /var/www/acme/.well-known/acme-challenge && chown -R 1000:1000 /var/www/acme && chmod 0755 /var/www/acme /var/www/acme/.well-known /var/www/acme/.well-known/acme-challenge'
```

The operations were:

```text
mkdir -p   Create the standard HTTP-01 directory hierarchy
chown      Make UID/GID 1000:1000 the owner
chmod 0755 Allow the owner to write and Nginx to read/traverse
```

Mode `0755` grants:

| Identity | Permissions |
|---|---|
| Owner | Read, write, and enter directory |
| Group | Read and enter directory |
| Others | Read and enter directory |

Root was used only for this initialization operation. Normal `step-cli`
commands still execute as UID 1000.

The challenge directory contains temporary public proof material, not private
keys. App1's private key remains in its separate certificate directory and is
not exposed through the HTTP webroot.

## Writing a simulated challenge token

The unprivileged client wrote a test response:

```powershell
docker compose --profile tools run --rm `
  --entrypoint sh `
  step-cli `
  -c 'printf "http-01-route-ok" > /var/www/acme/.well-known/acme-challenge/test-token'
```

Because this command succeeded after the ownership correction, UID 1000 has
the intended write access.

## Retrieving the token through Nginx

The test token was requested from the Windows host:

```powershell
curl.exe `
  --resolve app1.lab.local:8081:127.0.0.1 `
  http://app1.lab.local:8081/.well-known/acme-challenge/test-token
```

The expected and observed response was:

```text
http-01-route-ok
```

`--resolve` maps `app1.lab.local` to the local host for this curl invocation.
Port 8081 on Windows maps to port 80 in the App1 Nginx container.

## What this test proves

The successful response proves:

- The unprivileged ACME client can write challenge files.
- The named volume persists and is shared by the intended containers.
- Nginx can read the challenge directory through its read-only mount.
- The Nginx location maps the URL to the correct filesystem path.
- `app1.lab.local` reaches App1 from the Windows-host test path.
- HTTP traffic reaches Nginx on its container port 80.

It does not yet prove:

- An ACME account can be registered.
- An order can be created.
- `step-ca` can resolve and reach App1 over the Compose network.
- The CA will accept the challenge response.
- CSR finalization and certificate download will succeed.

Those behaviors are tested during the real ACME order.

## Troubleshooting map

| Symptom | Likely layer | Useful check |
|---|---|---|
| `Permission denied` while writing | Volume ownership | Run `id`; inspect UID/GID and mount mode |
| HTTP 404 | File absent or path mapping wrong | Confirm token exists under `.well-known/acme-challenge` |
| Connection refused | Nginx not running or port not published | `docker compose ps -a` |
| Wrong token content | Client wrote an incorrect response | Retrieve the URL and compare exact content |
| CA cannot resolve hostname | Compose DNS or network alias | Check that both services share `pki-network` |
| CA timeout | Routing, port, or service availability | Check Nginx logs and internal connectivity |

## Security properties

- The ACME client has no CA password or CA private-key access.
- The client has its own persistent state volume for account information.
- Nginx cannot modify challenge files because its webroot mount is read-only.
- Challenge data is isolated from App1's TLS private key.
- The CA and App1 communicate on the isolated Compose network.
- Host ports remain bound to `127.0.0.1`, preventing LAN exposure.

## Issuance result

The real ACME order completed successfully. The observed sequence was:

```text
Directory discovery
-> nonce retrieval
-> account creation
-> pending order for app1.lab.local
-> HTTP-01 authorization
-> Nginx returned the challenge response with HTTP 200
-> order became ready
-> CSR finalization
-> order became valid
-> certificate download
```

The CA issued `app1-acme.crt` with the configured eight-hour default lifetime.
It contains the leaf and intermediate certificates, chains to the lab root,
records the `lab-acme` ACME provisioner, and uses the public key from App1's
existing CSR.

After `nginx -t` succeeded, Nginx was reloaded without rebuilding its container.
The certificate fingerprint retrieved from the live TLS endpoint matched the
new file:

```text
8d224403bf12577f7c32fb9814b78e9563a77b7738b08fede3b1c2748ca22031
```

This proves Nginx actively deployed the ACME-issued identity while remaining
available. The manually issued certificate remains as superseded evidence and
a comparison artifact.

## Next step

The next phase creates `app2.lab.local` with an independent key, CSR, ACME
order, certificate, HTTP-01 webroot, and Nginx service. This demonstrates that
the design is repeatable rather than a one-off App1 configuration.
