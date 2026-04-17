#!/bin/bash
set -euo pipefail

echo "=== MARS DVR Backup Started: $(date) ==="

/scripts/pg_dump.sh

echo "[backup] Attempting Redis backup..."
/scripts/redis_dump.sh || echo "[backup] Redis backup skipped or failed (non-critical)"

echo "=== MARS DVR Backup Complete: $(date) ==="