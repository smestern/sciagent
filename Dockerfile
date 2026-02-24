# ── SciAgent Public Wizard — Production Dockerfile ─────────────────────
# Serves the public wizard + docs ingestor on a single port via Hypercorn.

FROM python:3.12-slim AS base

# Prevent Python from buffering stdout/stderr (important for Railway logs)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── System dependencies for Playwright/Chromium ───────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium rendering deps
    libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libatspi2.0-0 libxshmfence1 libx11-xcb1 libxcb-dri3-0 \
    # Additional X11 libs required by Chromium
    libxfixes3 libxext6 libxcursor1 libxi6 libxtst6 libxkbcommon0 \
    # Fonts so rendered pages aren't blank squares
    fonts-liberation fonts-dejavu-core \
    # Networking (for healthchecks)
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install Python dependencies ──────────────────────────────────────
COPY pyproject.toml README.md ./
COPY src/ src/
COPY templates/ templates/

RUN pip install --no-cache-dir ".[wizard]" && \
    pip install --no-cache-dir playwright && \
    python -m playwright install chromium

# ── Runtime configuration ────────────────────────────────────────────
# Railway provides $PORT dynamically (usually 8080).
# All other config comes from Railway environment variables.
ENV PORT=8080

EXPOSE ${PORT}

# ── Start with Hypercorn (production ASGI server) ────────────────────
# Single worker — required because session state, rate limits, and
# background tasks are all in-memory.
# Use shell form so $PORT is expanded at runtime.
CMD ["sh", "-c", "hypercorn 'sciagent_wizard:create_production_app()' --bind 0.0.0.0:${PORT:-8080} --workers 1 --access-log - --error-log -"]
