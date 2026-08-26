# First, build the application in the `/app` directory.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
RUN DJANGO_SECRET_KEY=build-only-static-collection-key \
    DATABASE_URL=postgresql://build:build@localhost/build \
    DJANGO_DEBUG=False \
    .venv/bin/python manage.py collectstatic --noinput

# Then, use a final image without uv
FROM python:3.12-slim-bookworm

RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --no-create-home app

# Copy the application from the builder
COPY --from=builder --chown=app:app /app /app

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Expose port 8000
EXPOSE 8000

USER app

CMD ["gunicorn", "--no-control-socket", "--bind", ":8000", "--workers", "2", "--timeout", "30", "--graceful-timeout", "30", "--max-requests", "1000", "--max-requests-jitter", "100", "--error-logfile", "-", "django_project.wsgi"]
