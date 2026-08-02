FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        file \
        gcc-mingw-w64-x86-64 \
        osslsigncode \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 signer

USER signer
WORKDIR /workspace

CMD ["bash"]
