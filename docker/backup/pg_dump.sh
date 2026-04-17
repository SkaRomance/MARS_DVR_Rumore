#!/bin/bash
set -euo pipefail
BACKUP_DIR="${BACKUP_DIR:-/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="mars_noise_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"
pg_dump -h "${PGHOST:-db}" -U "${PGUSER:-mars_noise}" "${PGDATABASE:-mars_noise}" \
    | gzip > "${BACKUP_DIR}/${FILENAME}"

echo "[backup] PostgreSQL saved: ${FILENAME}"

find "$BACKUP_DIR" -name "mars_noise_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
echo "[backup] Cleaned backups older than ${RETENTION_DAYS} days"