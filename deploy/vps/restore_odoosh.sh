#!/usr/bin/env bash
# Restores an Odoo.sh dump (.zip: dump.sql + filestore/) into the BelGoGreen
# instance, then updates our modules, cleans up and runs the final check of
# the Enterprise exit.
#
#   bash restore_odoosh.sh <dump.zip> [ee_exit.tgz]
#
# ee_exit.tgz: the ~/ee_exit folder of the Odoo.sh branch (counts saved
# before the uninstall), so the final check can compare them.
# Environment: DB (default belgogreen), BASE_URL (e.g. https://odoo.example.com,
# default http://localhost:8077), FORCE=1 to replace an existing database
# without asking.
#
# Disk: dump.sql is read straight from the zip and the filestore unzipped
# straight into the Odoo volume (no extra copy); the free space is checked
# first.
set -euo pipefail

ZIP=${1:?usage: restore_odoosh.sh <dump.zip> [ee_exit.tgz]}
EE_TGZ=${2:-}
DB=${DB:-belgogreen}
BASE=${BASE:-/opt/odoo-belgogreen}
BASE_URL=${BASE_URL:-http://localhost:8077}
command -v unzip >/dev/null || { echo "unzip is missing: apt install unzip" >&2; exit 1; }
ZIP=$(realpath "$ZIP")
[ -z "$EE_TGZ" ] || EE_TGZ=$(realpath "$EE_TGZ")

cd "$BASE"
set -a; . ./.env; set +a
dc() { docker compose "$@"; }
psql_db() { dc exec -T db psql -U "$POSTGRES_USER" "$@"; }
# a one-off Odoo container on the instance's volumes and config
odoo_run() { dc run --rm --no-deps -T "$@"; }
gb() { awk -v b="$1" 'BEGIN { printf "%.1f GB", b / 1e9 }'; }

WORK=$(mktemp -d "$BASE/restore/work.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

echo "== 1/7 Check the dump and the disk"
read -r sql_bytes fs_bytes fs_files < <(unzip -l "$ZIP" | awk '
    $4 == "dump.sql" { sql = $1 }
    $4 ~ /^filestore\/./ && $1 > 0 { fs += $1; n++ }
    END { printf "%d %d %d\n", sql, fs, n }')
[ "$sql_bytes" -gt 0 ] || { echo "No dump.sql in $ZIP" >&2; exit 1; }
[ "$fs_files" -gt 0 ] || echo "  WARNING: no filestore in the zip (dump made without filestore?)"
# the database (about twice the SQL, read straight from the zip), the filestore, 2 GB margin
need=$((sql_bytes * 2 + fs_bytes + 2000000000))
avail=$(df -B1 --output=avail "$BASE" | tail -1)
echo "  dump.sql $(gb "$sql_bytes"), filestore $(gb "$fs_bytes") ($fs_files files)"
echo "  needed about $(gb "$need"), free $(gb "$avail")"
if [ "$need" -gt "$avail" ]; then
    echo "Not enough free space: free some (old images: docker image prune) and run again." >&2
    exit 1
fi

echo "== 2/7 Database server"
dc up -d db
until dc exec -T db pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; do sleep 2; done
dc stop odoo >/dev/null 2>&1 || true
if [ -n "$(psql_db -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB'")" ]; then
    if [ "${FORCE:-}" != 1 ]; then
        read -r -p "Database $DB exists. Replace it (everything in it is lost)? [y/N] " answer
        [ "$answer" = y ] || [ "$answer" = Y ] || { echo "Stopped."; exit 1; }
    fi
    dc exec -T db dropdb -U "$POSTGRES_USER" "$DB"
fi
dc exec -T db createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" -E UTF8 -T template0 "$DB"

echo "== 3/7 Load the database (several minutes)"
unzip -p "$ZIP" dump.sql | psql_db -d "$DB" -q -o /dev/null 2> "$WORK/load_errors.log" || true
errors=$(grep -c 'ERROR' "$WORK/load_errors.log" || true)
if [ "$errors" != 0 ]; then
    echo "  $errors error(s) while loading (often harmless: roles or extensions of Odoo.sh):"
    grep 'ERROR' "$WORK/load_errors.log" | sort | uniq -c | head -20
    cp "$WORK/load_errors.log" "$BASE/restore/load_errors-$DB.log"
fi
modules=$(psql_db -d "$DB" -tAc "SELECT count(*) FROM ir_module_module WHERE state = 'installed'")
echo "  $modules modules installed in the dump"

echo "== 4/7 Filestore (straight into the Odoo volume)"
dc create odoo >/dev/null 2>&1    # creates the volume the first time
volume=$(docker volume inspect -f '{{.Mountpoint}}' "$(basename "$BASE")_odoo_web_data")
owner=$(odoo_run --entrypoint stat odoo -c '%u:%g' /var/lib/odoo)    # the odoo user of the image
rm -rf "$volume/filestore/$DB" "$volume/.restore"
mkdir -p "$volume/filestore" "$volume/.restore"
if [ "$fs_files" -gt 0 ]; then
    unzip -q "$ZIP" 'filestore/*' -d "$volume/.restore"
    mv "$volume/.restore/filestore" "$volume/filestore/$DB"
fi
rm -rf "$volume/.restore"
if [ -n "$EE_TGZ" ]; then
    mkdir -p "$WORK/ee" && tar xzf "$EE_TGZ" -C "$WORK/ee"
    src=$(ls "$WORK/ee/ee_exit" | head -1)
    rm -rf "$volume/ee_exit/$DB" && mkdir -p "$volume/ee_exit"
    cp -r "$WORK/ee/ee_exit/$src" "$volume/ee_exit/$DB"
    echo "  counts of the Enterprise exit: $(ls "$volume/ee_exit/$DB" | tr '\n' ' ')"
fi
chown -R "$owner" "$volume/filestore" "$volume/ee_exit" 2>/dev/null || chown -R "$owner" "$volume/filestore"
echo "  $(find "$volume/filestore/$DB" -type f 2>/dev/null | wc -l) files, $(du -sh "$volume/filestore/$DB" 2>/dev/null | cut -f1)"

echo "== 5/7 Settings for this server"
psql_db -d "$DB" -q <<SQL
-- links in emails and the reports' assets (PDFs are rendered inside the container)
INSERT INTO ir_config_parameter (key, value, create_date, write_date)
VALUES ('web.base.url', '$BASE_URL', now(), now()), ('report.url', 'http://127.0.0.1:8069', now(), now())
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = now();
-- a new identity: this database is not the Odoo.sh one
UPDATE ir_config_parameter SET value = gen_random_uuid()::text WHERE key = 'database.uuid';
DELETE FROM ir_config_parameter WHERE key IN ('database.enterprise_code', 'database.expiration_date',
                                              'database.expiration_reason');
-- the website's address is the one of the links sent with a website
-- (quotes, invoices): the Odoo.sh one would send customers to the old Odoo
UPDATE website SET domain = '$BASE_URL' WHERE domain LIKE '%.odoo.com%';
SQL
neutralized=$(psql_db -d "$DB" -tAc "SELECT value FROM ir_config_parameter WHERE key = 'database.is_neutralized'")
echo "  web.base.url = $BASE_URL; neutralized: ${neutralized:-no}"
echo "  websites: $(psql_db -d "$DB" -tAc "SELECT string_agg(name || ' ' || COALESCE(domain, '-'), ', ') FROM website")"
odoo_domains=$(psql_db -d "$DB" -tAc "SELECT string_agg(name, ', ') FROM mail_alias_domain WHERE name LIKE '%.odoo.com'")
if [ -n "$odoo_domains" ]; then
    echo "  ⚠️  email domains still on Odoo.sh: $odoo_domains (replies to Odoo's emails go to the old Odoo):"
    echo "     set your own domains in Settings > Technical > Email Domains (docs/ee_exit_runbook.md, Go-live)"
fi

echo "== 6/7 Update our modules (code of this server)"
odoo_run odoo odoo -d "$DB" -u bgg_custom_dev,belgogreen_sales_commission --stop-after-init --no-http \
    --log-level=warn

echo "== 7/7 Clean-up and final check of the Enterprise exit"
odoo_run odoo odoo shell -d "$DB" --no-http --log-level=error <<'PY'
exec(open('/mnt/extra-addons/belgogreen/tools/ee_exit/ee_uninstall.py').read())
ee_cleanup(env)
ee_final_check(env)
PY

dc up -d odoo
echo
echo "Odoo started: http://127.0.0.1:8077 on the server (SSH tunnel: ssh -L 8077:127.0.0.1:8077 <server>)"
echo "Once it is checked, the zip can go to free $(gb "$(stat -c %s "$ZIP")"): rm $ZIP"
