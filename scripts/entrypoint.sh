#!/bin/bash
# VPG Intelligence Digest - Docker entrypoint with environment validation

set -e

echo "=== VPG Intelligence Digest v6.0 ==="
echo "Starting environment validation..."

# Check required directories
for dir in data logs config; do
    if [ ! -d "/app/$dir" ]; then
        echo "Creating /app/$dir..."
        mkdir -p "/app/$dir"
    fi
done

mkdir -p /app/data/backups

# Validate required config files
MISSING=0
for f in business-units.json sources.json recipients.json scoring-weights.json industries.json; do
    if [ ! -f "/app/config/$f" ]; then
        echo "WARNING: Missing config file: $f"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -gt 0 ]; then
    echo "WARNING: $MISSING config file(s) missing. System may not function correctly."
fi

# Check credentials (warnings only — mock mode works without them)
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "NOTE: ANTHROPIC_API_KEY not set. AI scoring will use heuristic fallback."
fi

DELIVERY_MODE=${DELIVERY_MODE:-mock}
echo "Delivery mode: $DELIVERY_MODE"

if [ "$DELIVERY_MODE" = "smtp" ]; then
    if [ -z "$GMAIL_SENDER_EMAIL" ] || [ -z "$GMAIL_APP_PASSWORD" ]; then
        echo "WARNING: SMTP mode requires GMAIL_SENDER_EMAIL and GMAIL_APP_PASSWORD."
        echo "         Falling back to mock delivery."
    fi
fi

echo "Environment validation complete."
echo ""

# Execute the provided command
exec "$@"
