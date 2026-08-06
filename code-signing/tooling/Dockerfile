FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl \
        file \
        gcc-mingw-w64-x86-64 \
        osslsigncode \
    && rm -rf /var/lib/apt/lists/*

COPY code-signing-demo.sh /usr/local/bin/code-signing-demo

RUN chmod 0755 /usr/local/bin/code-signing-demo

RUN useradd --create-home --uid 1000 signer

USER signer
WORKDIR /workspace

CMD ["bash"]
