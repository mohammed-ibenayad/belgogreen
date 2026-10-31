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
  backups/                nightly database dumps
  restore/                where to upload the Odoo.sh dumps
```

Volumes: `odoo-belgogreen_odoo_db_data` (database), `odoo-belgogreen_odoo_web_data`
(filestore, sessions). Database name: `belgogreen`. Test address:
https://bgg.qadrin.com.

Sections 0–7 below are the **test server** setup (nginx + certbot), tested
with the restore of 2026-10-24. Production goes on its own VPS with Docker +
Traefik: next section.

## Production server (Hostinger KVM 4, Docker + Traefik)

Decided 2026-10-31. Hostinger KVM 4: 4 vCPU, 16 GB RAM, 200 GB NVMe, with
Hostinger's ready-made Docker + Traefik template. One VPS, three
environments, each its own Odoo container and PostgreSQL database:

| Environment | Address | Running | Data | Odoo workers | Memory limit (Odoo + database) |
|---|---|---|---|---|---|
| Production | erp.belgogreen.be | always | real | 4 + 1 cron | about 6 + 4 GB |
| Client staging | staging.erp.belgogreen.be | always | copy of production, neutralized | 2 | about 2 + 1 GB |
| BSI staging | bsi.erp.belgogreen.be | started and stopped when needed | copy of production, neutralized | 2 | about 2 + 1 GB |

- **Memory:** production + client staging about 13 GB; with the BSI staging
  running, tight but fine for short periods, with 4 GB of swap (section 0).
  Hard memory limits per container: a staging never takes production's.
- **Disk:** a staging's filestore links to production's files (hard links:
  Odoo never changes a stored file, it only adds new ones), so a staging
  costs its database (about 3 GB) and the files of its tests, not 31 GB.
  Estimate: production 34 GB, stagings about 8 GB, database backups about
  5 GB, images about 6 GB, system about 10 GB: about 65 GB of 200.
- **Isolation:** per environment its own folder, `.env`, `odoo.conf`
  (database name, `dbfilter`, `list_db = False`, its own master password),
  database and volumes.
- **Stagings neutralized** at every refresh from production
  (`odoo neutralize`: no outgoing mail server, no scheduled jobs, no payment
  provider), so a test never reaches a customer. The refresh replaces the
  "Reconstruire le Staging" button of Odoo.sh (`bgg_staging_rebuild` is
  not taken).
- **Backups:** production only (section 6), files off the server (open
  decision #9). The stagings are rebuilt from production.

**DNS of belgogreen.be:** A records `erp`, `staging.erp`, `bsi.erp` to the
VPS's IP, or `erp` + a wildcard `*.erp`.

**Traefik for Odoo** (what the template's defaults miss):

| Setting | Why |
|---|---|
| Route `/websocket` to the container's port 8072, the rest to 8069 | live updates (chat, notifications); otherwise "real-time connection lost" |
| Entry point `readTimeout` raised to about 600 s | Traefik v3 cuts requests after 60 s: big imports, large reports, DMS uploads |
| `proxy_mode = True` in `odoo.conf` | links built with https and the right address |
| Docker socket mounted read-only (or a socket proxy); dashboard off or protected | Traefik's access to Docker is access to the server |
| Compression and security headers middlewares | faster pages, safer site |

**The template's settings, to read on the VPS once ordered** (read only):
the Traefik version, the Docker network it watches, the entry point names,
the certificate resolver name, whether the dashboard is exposed.

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'
docker network ls
docker inspect $(docker ps -qf 'ancestor=traefik' | head -1) --format '{{json .Args}}{{json .Config.Labels}}'
find / -xdev \( -name 'traefik*.yml' -o -name 'traefik*.yaml' -o -name 'traefik*.toml' -o -name 'docker-compose.yml' \) -not -path '*/proc/*' 2>/dev/null | head
```

**Still to do** (to decide): the files of this folder target the test
server (nginx, one environment). For production they are adapted to the
template's Traefik (labels instead of nginx and certbot) and to the three
environments (one setup per environment, a staging refresh from
production); `restore_odoosh.sh` and `backup.sh` keep their role on the
production environment.

**Emails** (open decision #17): the companies' own domains as Odoo email
domains, one email provider sending for the three, each domain validated
with SPF, DKIM and DMARC, the outgoing mail server limited to those
domains ("FROM filtering"), `catchall@` of each domain delivered to Odoo.

| Company | Email domain today (Odoo.sh) | On production |
|---|---|---|
| AMSS MANAGEMENT SRL | belgogreen.odoo.com | belgogreen.be |
| BelGoGreen SASU | belgogreen.odoo.com (shared with AMSS) | belgogreen.fr (to confirm) |
| NATUR'ISOL SRL | naturisol.odoo.com | naturisol.be |

Users send from their own address when it is on one of the three domains
(22 @belgogreen.be, 6 @naturisol.be, 3 @belgogreen.fr); the others
(10 @gmail.com, 3 other domains) send as "Name" <notifications@company
domain>. Customer links use the one address erp.belgogreen.be for the
three companies.

## Sizes (bsi-staging dump, October 2026)

| | |
|---|---|
| Odoo.sh dump (zip with filestore) | 27 GB; upload about 50 min at 10 MB/s |
| `dump.sql` in it | 1.0 GB → database about 2–3 GB |
| Filestore unzipped | 31.2 GB, 47,541 files |
| Docker image | about 4 GB |
| Disk for the restore | zip + filestore + database: about 62 GB at the peak, 35 GB once the zip is deleted |
| Restore time | about 10 minutes (database 1 min, filestore 5 min, update and checks) |

## 0. Server

- Memory: the server has 7.8 GB, 2 vCPU, shared with the other instances.
  BelGoGreen is limited to 3 GB (Odoo) + 1.5 GB (PostgreSQL). Add swap so a
  peak does not kill a container:

  ```bash
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ```

- Tools: `apt install -y git unzip rsync tmux` (code, restore, backups, long
  commands that survive a dropped SSH session).

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
image (2–3 minutes the first time), starts the database. Safe to run
again (keeps `.env` and `odoo.conf`). "No services to build" is a harmless
message of Docker Compose.

## 3. Restore the Odoo.sh dump

Odoo.sh → the branch → Backups → **Create Backup**, then download the new
row of that branch (not the `main` rows: production) as a **neutralized**
dump **with filestore**.

From your computer, upload it under a fixed name (and, if you have it, the
`ee_exit.tgz` of the Odoo.sh branch: the counts saved before the uninstall):

```bash
scp belgogreen-bsi-staging-*.zip root@<server>:/opt/odoo-belgogreen/restore/staging.zip
```

On the server, check it arrived whole and the free space (see Sizes):

```bash
cd /opt/odoo-belgogreen
ls -lh restore/staging.zip
unzip -l restore/staging.zip dump.sql
df -h /
```

Then, inside `tmux new -s restore`:

```bash
BASE_URL=https://bgg.qadrin.com bash addons/belgogreen/deploy/vps/restore_odoosh.sh restore/staging.zip 2>&1 | tee restore/restore.log
```

(Add `restore/ee_exit.tgz` after the zip if you have it.) It:

1. checks the dump and the free space, and stops before changing anything
   if it does not fit;
2. replaces the database (asks first; `FORCE=1` does not ask);
3. loads `dump.sql` straight from the zip;
4. unzips the filestore straight into the Odoo volume;
5. sets the address (`BASE_URL`), the reports' address and a new database
   identity;
6. updates our modules (this server's code);
7. runs `ee_cleanup` and `ee_final_check` of the Enterprise exit
   (`docs/ee_exit_runbook.md`, Phase 6), then starts Odoo.

Known messages:
- `ERROR: extension "vector" is not available` (2 lines while loading):
  harmless, the extension of the Enterprise AI modules (uninstalled).
- `(ERROR/3) Unexpected indentation` during the update: the text of a
  module description, harmless.
- Final check: "Counts before the uninstall: not found" without
  `ee_exit.tgz`, "Database IS neutralized" for a staging copy.

The final check must end with "Ready for the dump ✅".

## 4. After the restore

Look at it before the domain, through an SSH tunnel from your computer:

```bash
ssh -L 8077:127.0.0.1:8077 root@<server>
```

then http://localhost:8077 (the "real-time connection lost" note is normal
without nginx). Open a few DMS documents and invoice PDFs: they prove the
filestore. Then free the zip:

```bash
rm /opt/odoo-belgogreen/restore/staging.zip
```

**Apps screen at login** (instead of Discuss): `web_responsive`'s "Redirect
to Home", per user (Settings → Users → Preferences; hidden when a Home
Action is set). For all internal users without a Home Action:

```bash
cd /opt/odoo-belgogreen
docker compose run --rm --no-deps -T odoo odoo shell -d belgogreen --no-http --log-level=error <<'PY'
users = env['res.users'].with_context(active_test=False).search([('share', '=', False), ('action_id', '=', False)])
users.write({'is_redirect_home': True})
env.cr.commit()
print("Apps screen at login: %s users" % len(users))
PY
```

**An administrator** (the rights of the main administrator, all companies,
a generated password printed once):

```bash
docker compose run --rm --no-deps -T odoo odoo shell -d belgogreen --no-http --log-level=error <<'PY'
import secrets
login, password = 'someone@example.com', secrets.token_urlsafe(12)
Users = env['res.users'].with_context(active_test=False, no_reset_password=True)
admin = env.ref('base.user_admin')
vals = {'name': 'Someone', 'login': login, 'email': login, 'password': password, 'active': True,
        'group_ids': [(6, 0, admin.group_ids.ids)],
        'company_ids': [(6, 0, env['res.company'].search([]).ids)], 'company_id': admin.company_id.id}
user = Users.search([('login', '=', login)], limit=1)
user.write(vals) if user else Users.create(vals)
env.cr.commit()
print("PASSWORD:", password)
PY
```

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

Every night a database dump in `backups/` (kept 14 days, a few hundred MB
each). The **filestore** (31 GB) is not copied to the server's own disk: it
would take the space the server does not have and not survive a disk
failure. Copy it off the server: set `FILESTORE_BACKUP_DIR` in the cron line
to a mounted remote (rclone mount, another disk) and the script mirrors it
there, or use Hostinger's VPS backups. Where: open decision #9.

Restore a backup: `pg_restore` the dump into a new database and copy the
filestore back into the volume's `filestore/belgogreen`.

## 7. Updating the code

```bash
cd /opt/odoo-belgogreen/addons/belgogreen && git pull
cd /opt/odoo-belgogreen
docker compose run --rm --no-deps -T odoo odoo -d belgogreen -u <modules changed> --stop-after-init --no-http --log-level=warn
docker compose restart odoo
```

Then Ctrl+F5 in the browser. A new Odoo 19 image (security fixes):
`docker compose build --pull && docker compose up -d`.

Do not restart the Docker service for BelGoGreen (Ubuntu suggests it after
updates): it stops every instance on the server.

## Everyday commands

```bash
cd /opt/odoo-belgogreen
docker compose ps                       # state
docker compose logs -f --tail 100 odoo  # Odoo log
docker compose restart odoo
docker compose run --rm --no-deps odoo odoo shell -d belgogreen --no-http   # Odoo shell
```

## At go-live

- On the production server (section "Production server"): restore the final
  dump into the production environment (production copy, see open decision
  #8 in `docs/ee_exit_open_decisions.md`), with `ee_exit.tgz` this time:
  `BASE_URL=https://erp.belgogreen.be MAIL_DOMAINS="belgogreen.odoo.com=belgogreen.be naturisol.odoo.com=naturisol.be"`;
  then belgogreen.fr for BelGoGreen SASU if confirmed (Settings → Technical →
  Email Domains). The final check's "GO-LIVE: TO DO BY HAND" lists what is
  left.
- The client staging, then the BSI staging when needed: refreshed from
  production, neutralized.
- A neutralized dump (staging copy): switch the outgoing mail server
  (Settings → Technical → Outgoing Mail Servers) and the scheduled jobs
  back on.
- Outgoing email: configure the company's SMTP server.
- Server size: see open decision #10.
