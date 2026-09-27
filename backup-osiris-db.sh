#!/bin/bash

set -e

DB="/home/parker/Osiris/data/osiris.db"
BACKUP_DIR="/home/parker/Osiris-backups/sqlite"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP="$BACKUP_DIR/osiris-$TIMESTAMP.db"

mkdir -p "$BACKUP_DIR"

sqlite3 "$DB" ".backup '$BACKUP'"

# Verify that the backup itself is a valid SQLite database.
RESULT=$(sqlite3 "$BACKUP" "PRAGMA integrity_check;")

if [ "$RESULT" != "ok" ]; then
    echo "Backup integrity check FAILED: $RESULT"
    rm -f "$BACKUP"
    exit 1
fi

# Delete backups older than 14 days.
find "$BACKUP_DIR" \
    -type f \
    -name "osiris-*.db" \
    -mtime +14 \
    -delete

echo "Osiris backup created successfully:"
echo "$BACKUP"
