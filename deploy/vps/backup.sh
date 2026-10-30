#!/usr/bin/env bash
# Nightly backup of the BelGoGreen instance, in /opt/odoo-belgogreen/backups:
# - the database (pg_dump, custom format), one per day, kept KEEP_DAYS days;
# - the filestore, mirrored (files are never changed, only added: the
#   mirror keeps every file, also the ones deleted since).
# Restore: pg_restore of a dump + the filestore folder.
# Same disk as the server: copy backups/ elsewhere too (see README).
set -euo pipefail

BASE=${BASE:-/opt/odoo-belgogreen}
DB=${DB:-belgogreen}
KEEP_DAYS=${KEEP_DAYS:-14}
OUT="$BASE/backups"

command -v rsync >/dev/null || { echo "rsync is missing: apt install rsync" >&2; exit 1; }
cd "$BASE"
set -a; . ./.env; set +a
mkdir -p "$OUT/filestore"
stamp=$(date +%Y%m%d-%H%M)

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -Fc "$DB" > "$OUT/.$DB-$stamp.dump"
mv "$OUT/.$DB-$stamp.dump" "$OUT/$DB-$stamp.dump"

volume=$(docker volume inspect -f '{{.Mountpoint}}' "$(basename "$BASE")_odoo_web_data")
rsync -a "$volume/filestore/$DB/" "$OUT/filestore/$DB/"

find "$OUT" -maxdepth 1 -name "$DB-*.dump" -mtime +"$KEEP_DAYS" -delete
echo "$(date '+%F %T') backup $DB-$stamp.dump ($(du -h "$OUT/$DB-$stamp.dump" | cut -f1)), filestore $(du -sh "$OUT/filestore/$DB" | cut -f1)"
