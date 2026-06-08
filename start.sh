#!/bin/bash
export FLASK_SECRET_KEY="${FLASK_SECRET_KEY:-inflatable2026secretkey}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

echo "=== Starting inflatable-model ==="
echo "Python version: $(python --version)"
echo "PORT: ${PORT}"

# Start with gunicorn
exec gunicorn app:app --bind "0.0.0.0:${PORT:-10000}" --workers 1 --timeout 120 --log-level info --access-logfile - --error-logfile -
