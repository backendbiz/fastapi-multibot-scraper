# ==============================================================================
# FastAPI Production Server - Dockerfile
# With Selenium Chrome for Web Scraping & Telegram Integration
# Optimized for deployment on Coolify and other Docker-based platforms
# ==============================================================================

# Stage 1: Build stage
FROM python:3.12-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# ==============================================================================
# Stage 2: Production stage
# ==============================================================================
FROM python:3.12-slim as production

# Labels for container metadata
LABEL maintainer="your-email@example.com" \
    version="1.0.0" \
    description="FastAPI Server with Selenium Scraping and Telegram Integration"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Application settings
    ENVIRONMENT=production \
    DEBUG=false \
    HOST=0.0.0.0 \
    PORT=3000 \
    # Chrome settings
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    DISPLAY=:99

# Install runtime dependencies including Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    # Chromium and ChromeDriver
    chromium \
    chromium-driver \
    # Required for Chrome
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    # Fonts
    fonts-liberation \
    fonts-noto-color-emoji \
    # Virtual display for headless
    xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy wheels from builder stage and install
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY --chown=appuser:appgroup ./app ./app

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/screenshots \
    && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Run the application with Gunicorn + Uvicorn workers
CMD ["sh", "-c", "gunicorn app.main:app --workers ${WORKERS:-4} --worker-class uvicorn.workers.UvicornWorker --bind ${HOST:-0.0.0.0}:${PORT:-3000} --access-logfile - --error-logfile - --capture-output --timeout 120"]
