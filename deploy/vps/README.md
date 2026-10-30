# BelGoGreen on the VPS (Odoo 19 Community + OCA, Docker)

Same layout as the other Odoo instances on the server (`/opt/<name>`, Odoo
and its own PostgreSQL 16, ports on 127.0.0.1 behind nginx, certbot):

```
/opt/odoo-belgogreen/
  docker-compose.yml      odoo-belgogreen (127.0.0.1:8077 web, :8078 websocket) + odoo-belgogreen-db
  Dockerfile              odoo:19.0 + matplotlib, numpy, WeasyPrint, rasterio, cssselect
  .env                    database user and password (generated)
  config/odoo.conf        generated from odoo.conf.template (master password generated)
  addons/belgogreen/      this repository (git clone), mounted read-only
  backups/                nightly database dumps + filestore mirror
  restore/                where to upload the Odoo.sh dumps
```

Volumes: `odoo-belgogreen_odoo_db_data` (database), `odoo-belgogreen_odoo_web_data`
(filestore, sessions). Database name: `belgogreen`.

## 0. Server

- Memory: the server has 7.8 GB, 2 vCPU and **no swap**, shared with the
  other instances. BelGoGreen is limited to 3 GB (Odoo) + 1.5 GB
  (PostgreSQL). Add swap so a peak does not kill a container:

  ```bash
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ```

- Tools: `apt install -y git unzip rsync` (code, restore, backups).

## 1. Code

**Public repository** (HTTPS, nothing to set up):

```bash
mkdir -p /opt/odoo-belgogreen/addons
git clone -b bgg_ee_exit https://github.com/mohammed-ibenayad/belgogreen.git /opt/odoo-belgogreen/addons/belgogreen
```

A clone made while the repository is public keeps working once it is made
private again, except `git pull`: then switch to a deploy key (below) and
`git -C /opt/odoo-belgogreen/addons/belgogreen remote set-url origin github-belgogreen:mohammed-ibenayad/belgogreen.git`.

**Private repository**: give the server read access with a deploy key.

```bash
ssh-keygen -t ed25519 -N '' -f ~/.ssh/belgogreen_deploy -C "vps belgogreen (read only)"
cat ~/.ssh/belgogreen_deploy.pub
```

GitHub → the repository → Settings → Deploy keys → Add deploy key: paste
it, **without** write access. Then:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-belgogreen
    HostName github.com
    User git
    IdentityFile ~/.ssh/belgogreen_deploy
EOF
mkdir -p /opt/odoo-belgogreen/addons
git clone -b bgg_ee_exit github-belgogreen:mohammed-ibenayad/belgogreen.git /opt/odoo-belgogreen/addons/belgogreen
```

(For the test: branch `bgg_ee_exit`. At go-live: the production branch.)

## 2. Instance

```bash
bash /opt/odoo-belgogreen/addons/belgogreen/deploy/vps/setup.sh
```

Creates the layout, generates `.env` and `config/odoo.conf`, builds the
image (a few minutes the first time), starts the database. Safe to run
again (keeps `.env` and `odoo.conf`).

## 3. Restore the Odoo.sh dump

From your computer, upload the dump (zip **with filestore**) and the
`ee_exit.tgz` of the Odoo.sh branch:

```bash
scp belgogreen-bsi-staging-*.zip ee_exit.tgz root@<server>:/opt/odoo-belgogreen/restore/
```

On the server:

```bash
cd /opt/odoo-belgogreen
BASE_URL=https://bgg.qadrin.com bash addons/belgogreen/deploy/vps/restore_odoosh.sh restore/<dump>.zip restore/ee_exit.tgz
```

It loads the database, copies the filestore, sets the URL and a new
database identity, updates our modules (this server's code), runs
`ee_cleanup` and `ee_final_check` of the Enterprise exit (see
`docs/ee_exit_runbook.md`, Phase 6), then starts Odoo. Read the final
check: it must end with "Ready for the dump ✅" (⚠️ lines are known points; the wording comes from the Odoo.sh steps).

Options: `BASE_URL`, the address used in emails and links
(`https://bgg.qadrin.com` for now),
`FORCE=1` to replace the database without asking. Running it again
replaces the database with the dump.

## 4. Look at it before the domain

Through an SSH tunnel from your computer:

```bash
ssh -L 8077:127.0.0.1:8077 root@<server>
```

Then open http://localhost:8077 and log in with your Odoo.sh login and
password. (Without nginx the "real-time connection lost" note is normal.)

## 5. Domain and HTTPS (bgg.qadrin.com)

DNS of qadrin.com: an **A record** `bgg` → the server's IP (as for
`three60group` and `odoo`). `dig +short bgg.qadrin.com` must answer the
server's IP before certbot. Then:

```bash
sed 's/__DOMAIN__/bgg.qadrin.com/' /opt/odoo-belgogreen/addons/belgogreen/deploy/vps/nginx-belgogreen.conf \
    > /etc/nginx/sites-available/belgogreen
ln -s /etc/nginx/sites-available/belgogreen /etc/nginx/sites-enabled/belgogreen
nginx -t && systemctl reload nginx
certbot --nginx -d bgg.qadrin.com
```

Restored with another `BASE_URL`? Set the address:

```bash
docker exec odoo-belgogreen-db psql -U odoo_belgogreen -d belgogreen -c \
    "UPDATE ir_config_parameter SET value = 'https://bgg.qadrin.com' WHERE key = 'web.base.url'"
```

## 6. Backups

```bash
echo '30 2 * * * root bash /opt/odoo-belgogreen/addons/belgogreen/deploy/vps/backup.sh >> /opt/odoo-belgogreen/backups/backup.log 2>&1' \
    > /etc/cron.d/odoo-belgogreen-backup
```

Every night: a database dump (kept 14 days) and the filestore mirrored in
`backups/`. They are on the same disk as the server: also copy `backups/`
off the server (Hostinger backups / snapshots, or rclone to cloud storage).

Restore a backup: `pg_restore` the dump into a new database and copy
`backups/filestore/belgogreen` into the volume's `filestore/`.

## 7. Updating the code

```bash
cd /opt/odoo-belgogreen/addons/belgogreen && git pull
cd /opt/odoo-belgogreen
docker compose run --rm odoo odoo -d belgogreen -u <modules changed> --stop-after-init --no-http
docker compose restart odoo
```

A new Odoo 19 image (security fixes): `docker compose build --pull && docker compose up -d`.

## Everyday commands

```bash
cd /opt/odoo-belgogreen
docker compose ps                     # state
docker compose logs -f --tail 100 odoo  # Odoo log
docker compose restart odoo
docker compose run --rm odoo odoo shell -d belgogreen --no-http   # Odoo shell
```

## At go-live

- Restore the final dump the same way (production copy, see the open
  decision #8 in `docs/ee_exit_open_decisions.md`).
- A neutralized dump (staging copy): switch the outgoing mail server
  (Settings → Technical → Outgoing Mail Servers) and the scheduled jobs
  back on.
- Outgoing email: configure the company's SMTP server.
