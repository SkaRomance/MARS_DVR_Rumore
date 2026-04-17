#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SSL_DIR="${SCRIPT_DIR}/ssl"

if [ -f "${SSL_DIR}/cert.pem" ] && [ -f "${SSL_DIR}/key.pem" ]; then
    echo "[ssl] Certificates already exist in ${SSL_DIR}, skipping."
    exit 0
fi

mkdir -p "${SSL_DIR}"
echo "[ssl] Generating self-signed certificate (dev/staging only)..."
openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "${SSL_DIR}/key.pem" \
    -out "${SSL_DIR}/cert.pem" \
    -subj "/CN=mars-dvr-local"
echo "[ssl] Done. For production: use Let's Encrypt or provide your own certificates."