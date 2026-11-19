# Single image for web and worker. The default PyTorch wheel pulled by Whisper
# runs on CPU and also uses an NVIDIA GPU when the container is given one.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DATA_DIR=/data \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.8 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN DATA_DIR=/tmp/build-data python manage.py collectstatic --noinput \
    && rm -rf /tmp/build-data

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data /home/app/.cache/whisper \
    && chown -R app:app /data /home/app/.cache
USER app

EXPOSE 8000
