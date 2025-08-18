# Multi-stage build for smaller image and faster installs
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=off \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# System deps (build-essential often needed for scientific python wheels)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application
COPY app ./app
COPY run.py config.py ./

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Flask/Gunicorn
ENV FLASK_CONFIG=production \
    PORT=8000
EXPOSE 8000

# Default command
CMD ["gunicorn", "-w", "2", "-k", "gthread", "-b", "0.0.0.0:8000", "run:app"]

