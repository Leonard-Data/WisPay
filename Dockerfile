# syntax=docker/dockerfile:1.7
#
# WisPay single-container deploy image.
#
# This image bundles the Reflex 0.9.8 app (backend ASGI + compiled
# frontend bundle) into a single artifact that can ship to Azure
# Container Apps, Azure App Service (Linux), Kubernetes, or any
# container host that exposes the configured port. It does NOT bake
# the production database URL or tenant secrets — every secret is read
# from the environment at runtime (CONVENTIONS.md security rule 6).
#
# Build:
#   docker build -t wispay:latest .
#
# Run with the SQLite dev default (demo seed activated):
#   docker run --rm -p 8000:8000 \
#     -e WISPAY_DEMO_MODE=1 \
#     -e WS_DB_URL=sqlite:///./wispay.db \
#     wispay:latest
#
# Run against Azure SQL (production-shape):
#   docker run --rm -p 8000:8000 \
#     -e AZURE_SQL_SERVER=... -e AZURE_SQL_DATABASE=... \
#     -e AZURE_SQL_USERNAME=... -e AZURE_SQL_PASSWORD=... \
#     -e AZURE_ENTRA_TENANT_ID=... -e AZURE_ENTRA_CLIENT_ID=... \
#     -e AZURE_ENTRA_CLIENT_SECRET=... \
#     wispay:latest
#
# The image exposes ONE port (8000) that serves both the API and the
# compiled frontend (Reflex serves the static bundle from the same
# ASGI process in production). That is the "single-binary" simplification:
# one container, one process group, one health probe target.

ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/wispay/.venv

WORKDIR /opt/wispay

# uv is the only tool we need from PyPI to bootstrap the project.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.5.* && \
    uv sync --frozen --no-dev --no-install-project

# Production extras — pyodbc for Azure SQL, msal for Entra ID SSO.
RUN uv sync --frozen --no-dev --no-install-project \
        --extra azure --extra entra

COPY . /opt/wispay

# Compile the frontend bundle; this is what `reflex run` would do at
# startup in dev mode. In production we bake the bundle into the image.
RUN uv run --no-sync reflex export --backend-only=false --no-source-map

FROM python:${PYTHON_VERSION}-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/wispay/.venv/bin:/usr/local/bin:${PATH}" \
    WS_DB_URL=sqlite:///./wispay.db \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /opt/wispay

# Copy the resolved venv + compiled bundle + source. We keep the runtime
# image slim because the builder already pulled them.
COPY --from=builder /opt/wispay/.venv /opt/wispay/.venv
COPY --from=builder /opt/wispay/.web /opt/wispay/.web
COPY --from=builder /opt/wispay/WisPay /opt/wispay/WisPay
COPY --from=builder /opt/wispay/states /opt/wispay/states
COPY --from=builder /opt/wispay/assets /opt/wispay/assets
COPY --from=builder /opt/wispay/scripts /opt/wispay/scripts
COPY --from=builder /opt/wispay/rxconfig.py /opt/wispay/rxconfig.py

# `python -m` is the canonical, signal-safe entry point. It is what
# validates the application boots and exits when the container stops.
# `reflex run --env prod` listens on $APP_PORT and serves the
# pre-compiled frontend bundle from .web.
CMD ["sh", "-c", "python /opt/wispay/scripts/serve.py"]

EXPOSE 8000
