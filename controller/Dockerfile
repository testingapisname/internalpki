FROM smallstep/step-ca:0.30.2 AS smallstep

FROM python:3.12-alpine

COPY --from=smallstep /usr/local/bin/step /usr/local/bin/step
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && addgroup -g 1000 controller \
    && adduser -D -u 1000 -G controller controller

USER 1000:1000
ENTRYPOINT ["pki-controller"]
CMD ["--config", "/config/controller.toml"]

