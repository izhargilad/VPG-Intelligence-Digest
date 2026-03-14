FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright and Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    cron \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build React UI
COPY src/ui/package*.json src/ui/
RUN cd src/ui && npm ci --production=false

COPY src/ui/ src/ui/
RUN cd src/ui && npm run build

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p data logs output config data/backups

# Phase 6: Entrypoint script for env validation
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose API port
EXPOSE 8000

# Health check: verify API is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/system/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]

# Default: run the API server
CMD ["python", "-m", "src.api.server"]
