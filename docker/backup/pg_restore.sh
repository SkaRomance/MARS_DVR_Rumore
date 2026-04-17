#!/bin/bash
set -euo pipefail
if [ -z "${1:-}" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
    echo "[restore] File not found: $BACKUP_FILE"
    exit 1
fi

echo "[restore] Restoring PostgreSQL from: $BACKUP_FILE"
gunzip -c "$BACKUP_FILE" | psql -h "${PGHOST:-db}" -U "${PGUSER:-mars_noise}" "${PGDATABASE:-mars_noise}"
echo "[restore] PostgreSQL restore complete."