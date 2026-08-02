#!/bin/sh
set -eu

certificate="${TLS_CERTIFICATE_PATH:?TLS_CERTIFICATE_PATH is required}"
echo "certificate watcher: monitoring $certificate"

(
    previous="$(sha256sum "$certificate" | awk '{print $1}')"
    while sleep 5; do
        current="$(sha256sum "$certificate" | awk '{print $1}')"
        if [ "$current" != "$previous" ]; then
            if nginx -t; then
                nginx -s reload
                previous="$current"
                echo "certificate watcher: reloaded $certificate"
            else
                echo "certificate watcher: validation failed for $certificate" >&2
            fi
        fi
    done
) &
