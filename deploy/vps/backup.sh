#!/usr/bin/env bash
# Nightly backup of the BelGoGreen instance:
# - the database (pg_dump, custom format) in /opt/odoo-belgogreen/backups,
#   one per day, kept KEEP_DAYS days (a few hundred MB each);
# - the filestore (31 GB in October 2026) only when FILESTORE_BACKUP_DIR
#   points to another disk or a mounted remote (rclone mount, NFS...):
#   mirrored there (files are never changed, only added, so the mirror keeps
#   every file, also the ones deleted since). Not on the server's own disk:
#   it would double the space and not survive a disk failure.
# Restore: pg_restore of a dump + the filestore folder.
set -euo pipefail

BASE=${BASE:-/opt/odoo-belgogreen}
DB=${DB:-belgogreen}
KEEP_DAYS=${KEEP_DAYS:-14}
FILESTORE_BACKUP_DIR=${FILESTORE_BACKUP_DIR:-}
OUT="$BASE/backups"

cd "$BASE"
set -a; . ./.env; set +a
mkdir -p "$OUT"
stamp=$(date +%Y%m%d-%H%M)

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -Fc "$DB" > "$OUT/.$DB-$stamp.dump"
mv "$OUT/.$DB-$stamp.dump" "$OUT/$DB-$stamp.dump"
find "$OUT" -maxdepth 1 -name "$DB-*.dump" -mtime +"$KEEP_DAYS" -delete
echo "$(date '+%F %T') database $DB-$stamp.dump ($(du -h "$OUT/$DB-$stamp.dump" | cut -f1))"

if [ -n "$FILESTORE_BACKUP_DIR" ]; then
    command -v rsync >/dev/null || { echo "rsync is missing: apt install rsync" >&2; exit 1; }
    volume=$(docker volume inspect -f '{{.Mountpoint}}' "$(basename "$BASE")_odoo_web_data")
    mkdir -p "$FILESTORE_BACKUP_DIR/$DB"
    rsync -a "$volume/filestore/$DB/" "$FILESTORE_BACKUP_DIR/$DB/"
    echo "$(date '+%F %T') filestore mirrored to $FILESTORE_BACKUP_DIR/$DB"
else
    echo "$(date '+%F %T') filestore not copied (FILESTORE_BACKUP_DIR not set)"
fi
