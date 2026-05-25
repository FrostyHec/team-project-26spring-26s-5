# syntax=docker/dockerfile:1.7

ARG NODE_IMAGE=node:20-bookworm-slim
ARG PYTHON_IMAGE=ghcr.io/astral-sh/uv:python3.12-bookworm-slim

FROM ${NODE_IMAGE} AS gui-builder

ENV PNPM_HOME=/pnpm
ENV PATH="${PNPM_HOME}:${PATH}"

WORKDIR /app/packages/gui

RUN corepack enable

COPY packages/gui/package.json packages/gui/pnpm-lock.yaml packages/gui/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY packages/gui/ ./
RUN pnpm build

FROM ${PYTHON_IMAGE} AS app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1
ENV DATA_PATH=/data
ENV DB_PATH=/data
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV PATH="/app/packages/cli/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates gosu libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY packages/core/pyproject.toml packages/core/uv.lock packages/core/README.md packages/core/
COPY packages/cli/pyproject.toml packages/cli/uv.lock packages/cli/README.md packages/cli/
COPY packages/core/src packages/core/src
COPY packages/cli/src packages/cli/src
COPY scripts/docker/entrypoint.sh /usr/local/bin/sustech-campus-assistant-entrypoint

RUN uv sync --directory packages/cli --frozen --no-dev

COPY --from=gui-builder /app/packages/gui/dist /app/packages/gui/dist

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && mkdir -p /data \
    && chmod +x /usr/local/bin/sustech-campus-assistant-entrypoint \
    && chown -R app:app /app /data

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import json, os, urllib.request; port = os.getenv('APP_PORT', '8000'); response = urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=3); data = json.load(response); raise SystemExit(0 if data.get('status') == 'ok' else 1)"

ENTRYPOINT ["sustech-campus-assistant-entrypoint"]
CMD ["agent-cli", "serve", "--static-dir", "/app/packages/gui/dist"]
