#!/bin/bash
set -euo pipefail
BACKUP_DIR="${BACKUP_DIR:-/backups/redis}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "[backup] Triggering Redis BGSAVE..."
redis-cli -h "${REDISHOST:-redis}" BGSAVE || true
sleep 2

if [ -f /data/dump.rdb ]; then
    cp /data/dump.rdb "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"
else
    echo "[backup] Warning: /data/dump.rdb not found inside container."
    redis-cli -h "${REDISHOST:-redis}" --rdb "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb" BGSAVE || true
fi

echo "[backup] Redis saved: redis_${TIMESTAMP}.rdb"

find "$BACKUP_DIR" -name "redis_*.rdb" -mtime +"$RETENTION_DAYS" -delete
echo "[backup] Cleaned Redis backups older than ${RETENTION_DAYS} days"