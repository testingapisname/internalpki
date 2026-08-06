FROM python:3.13-slim-bookworm

RUN apt-get update \
    && apt-get install --yes --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

COPY tsa.conf server.py /app/

RUN useradd --create-home --uid 1000 tsa \
    && mkdir -p /state \
    && chown tsa:tsa /state

USER tsa
WORKDIR /app

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=2).read()"

CMD ["python", "/app/server.py"]
