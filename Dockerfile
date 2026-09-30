# syntax=docker/dockerfile:1
FROM python:3.14-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 care
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
COPY examples /app/examples
WORKDIR /app
RUN mkdir -p /data && chown care:care /data
USER care
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"
ENTRYPOINT ["care-voice"]
CMD ["serve", "--config", "/app/examples/care-voice.yaml", "--db", "/data/care-voice.db", "--host", "0.0.0.0", "--port", "8080"]
