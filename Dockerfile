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
RUN mkdir -p data logs output config

# Expose API port
EXPOSE 8000

# Default: run the API server
CMD ["python", "-m", "src.api.server"]
