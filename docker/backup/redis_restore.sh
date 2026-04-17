#!/bin/bash
set -euo pipefail
if [ -z "${1:-}" ]; then
    echo "Usage: $0 <redis_backup.rdb>"
    exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
    echo "[restore] File not found: $BACKUP_FILE"
    exit 1
fi

echo "[restore] Restoring Redis from: $BACKUP_FILE"
echo "[restore] Stopping Redis writes..."
redis-cli -h "${REDISHOST:-redis}" BGREWRITEAOF || true
sleep 1

cp "$BACKUP_FILE" /data/dump.rdb
echo "[restore] Redis dump.rdb replaced. Restart Redis to load the new data."
echo "[restore] Run: docker compose restart redis"