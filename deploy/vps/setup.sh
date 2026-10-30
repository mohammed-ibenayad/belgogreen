#!/usr/bin/env bash
# Creates (or refreshes) the BelGoGreen instance in /opt/odoo-belgogreen,
# laid out like the other instances: docker-compose.yml, .env, config/,
# addons/ (our repository, cloned before), backups/.
# Safe to run again: keeps .env and config/odoo.conf, rebuilds the image.
set -euo pipefail

BASE=${BASE:-/opt/odoo-belgogreen}
SRC="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$BASE/addons/belgogreen/.git" ]; then
    echo "Clone the repository first: git clone -b <branch> <repository> $BASE/addons/belgogreen" >&2
    exit 1
fi

mkdir -p "$BASE/config" "$BASE/backups" "$BASE/restore"
cp "$SRC/docker-compose.yml" "$SRC/Dockerfile" "$BASE/"

if [ ! -f "$BASE/.env" ]; then
    (umask 077; printf 'POSTGRES_USER=odoo_belgogreen\nPOSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)" > "$BASE/.env")
    echo "Created $BASE/.env (database password)"
fi
if [ ! -f "$BASE/config/odoo.conf" ]; then
    sed "s/__ADMIN_PASSWD__/$(openssl rand -hex 24)/" "$SRC/odoo.conf.template" > "$BASE/config/odoo.conf"
    chmod 644 "$BASE/config/odoo.conf"
    echo "Created $BASE/config/odoo.conf (master password: admin_passwd in it)"
fi

cd "$BASE"
docker compose build --pull
docker compose up -d db
echo
echo "Ready. Next: restore a dump with"
echo "  bash $SRC/restore_odoosh.sh <dump.zip> [ee_exit.tgz]"
