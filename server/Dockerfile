# The dependencies are installed in one image and copied into another that has no build tools.
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# First the dependencies alone, so this layer is rebuilt only when the lockfile changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

FROM python:3.13-slim-trixie
RUN groupadd --system --gid 999 nonroot \
    && useradd --system --gid 999 --uid 999 nonroot \
    && mkdir /data \
    && chown nonroot:nonroot /data
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    INBOX_DATA_DIR=/data
VOLUME /data
USER nonroot
EXPOSE 8000
CMD ["uvicorn", "innersight_inbox.app:create_app_from_environment", "--factory", "--host", "0.0.0.0", "--port", "8000"]
