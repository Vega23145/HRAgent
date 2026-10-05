# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_NO_CACHE=1

WORKDIR /srv

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-install-project

COPY src ./src

# Install the project if needed:
# RUN uv sync --locked --no-dev

FROM python:3.13-slim-bookworm AS runtime

ENV PATH="/srv/.venv/bin:$PATH" \
    PYTHONPATH="/srv/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INTERVAL=3600

WORKDIR /srv

COPY --from=builder /srv/.venv /srv/.venv
COPY --from=builder /srv/src ./src

RUN useradd --system \
        --uid 998 \
        --no-create-home \
        --shell /usr/sbin/nologin \
        hub \
    && chown -R hub:hub /srv

USER hub

CMD ["sh", "-c", "python -m resumepipeline.resume_pipeline --loop $INTERVAL"]
