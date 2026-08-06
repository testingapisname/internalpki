FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl \
        openssl \
    && rm -rf /var/lib/apt/lists/*

COPY tls-demo.sh /usr/local/bin/tls-demo

RUN chmod 0755 /usr/local/bin/tls-demo \
    && useradd --create-home --uid 1000 demo

USER demo
WORKDIR /workspace

CMD ["tls-demo"]
