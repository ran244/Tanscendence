#!/bin/sh
set -e
mkdir -p /etc/nginx/ssl
if [ ! -f /etc/nginx/ssl/server.crt ] || [ ! -f /etc/nginx/ssl/server.key ]; then
  echo "Generating a disposable self-signed TLS certificate for local evaluation..."
  if command -v openssl >/dev/null 2>&1; then
    openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
      -keyout /etc/nginx/ssl/server.key \
      -out /etc/nginx/ssl/server.crt \
      -subj "/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,DNS:127.0.0.1" 2>/dev/null || \
      openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
        -keyout /etc/nginx/ssl/server.key \
        -out /etc/nginx/ssl/server.crt \
        -subj "/CN=localhost"
  else
    echo "openssl not available; TLS will fail. Mount your own certs at /etc/nginx/ssl/server.{crt,key}." >&2
    exit 1
  fi
fi
exec nginx -g "daemon off;"