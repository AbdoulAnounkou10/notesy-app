#!/bin/bash
# Exit immediately if any command fails
# Without this, if migrate fails, gunicorn starts anyway against a broken schema
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting gunicorn..."
# bind: listen on all interfaces port 8000
# workers: 2 processes handling requests
# threads: 4 threads per worker for concurrent requests
# timeout: kill a worker if it takes longer than 60s
exec gunicorn notesy.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 4 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -