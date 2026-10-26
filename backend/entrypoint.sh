#!/bin/sh
set -e

echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
until python -c "
import os, socket, sys
s = socket.socket()
try:
    s.connect((os.getenv('POSTGRES_HOST', 'db'), int(os.getenv('POSTGRES_PORT', '5432'))))
except Exception:
    sys.exit(1)
"; do
  sleep 2
done
echo "PostgreSQL is up."

if [ "${RUN_STARTUP_TASKS:-false}" = "true" ]; then
  echo "Applying migrations..."
  python manage.py migrate --noinput

  echo "Collecting static files..."
  python manage.py collectstatic --noinput

  echo "Seeding demo data if SEED_DEMO=true..."
  python manage.py seed_demo
else
  echo "Startup tasks are owned by the backend service; skipping them for ${SERVICE_NAME:-service}."
fi

echo "Starting $SERVICE_NAME..."
exec "$@"
