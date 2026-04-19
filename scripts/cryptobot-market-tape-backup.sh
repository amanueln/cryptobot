#!/bin/bash
# Hourly online backup of market_tape.db (container overlay -> host-mounted /backup).
# Uses SQLite online-backup API (WAL-safe, atomic) then gzip -9.
# Rotation: keep last 24 hourly (~1 day).
set -euo pipefail

HOST_DIR=/DATA/.media/Media20TB/cryptobotBackup/hourly
mkdir -p "$HOST_DIR"
TS=$(date +%Y%m%d_%H%M)
CONTAINER_OUT="/backup/hourly/market_tape_${TS}.db"
HOST_OUT="${HOST_DIR}/market_tape_${TS}.db"

PY_SCRIPT="import sqlite3, os; os.makedirs('/backup/hourly', exist_ok=True); s=sqlite3.connect('/app/src/data/market_tape.db'); d=sqlite3.connect('${CONTAINER_OUT}'); s.backup(d); s.close(); d.close(); print('backup_ok')"

docker exec cryptobot python3 -c "$PY_SCRIPT"

gzip -9 "${HOST_OUT}"

mapfile -t OLD_SNAPS < <(ls -1t "${HOST_DIR}"/market_tape_*.db.gz 2>/dev/null | tail -n +25)
for f in "${OLD_SNAPS[@]}"; do rm -f "$f"; done
find "${HOST_DIR}" -maxdepth 1 -name 'market_tape_*.db' -mmin +60 -delete 2>/dev/null || true
exit 0
