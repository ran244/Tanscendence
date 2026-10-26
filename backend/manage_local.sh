#!/bin/sh
# Load local development/test environment variables and run a Django command.
set -a
if [ -f .env.local ]; then
  . ./.env.local
fi
if [ -f ../.env ]; then
  . ../.env
fi
set +a
exec .venv/bin/python manage.py "$@"