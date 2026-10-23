# Enterprise exit: runbook (Odoo.sh part)

The steps run on Odoo.sh, in this order, to turn a copy of production into
a database without Enterprise, ready to restore on the Community server.
Rehearsed on a throw-away staging branch first; repeated on the final
production copy at go-live.

Every shell step starts in a **new** shell (`odoo-bin shell --no-http`):
a shell left open loses its database connection.

## 0. Branch

- Rehearsal: in GitHub, create the branch `ee-exit-rehearsal` from
  `bsi-staging`; in Odoo.sh, put it in **Staging**. The build copies
  production and updates the changed modules (bgg_custom_dev migrations:
  RDV fields, Studio port, RDV type commercials).
- Wait for the build to be green.

## 1. Install DMS

```python
env['ir.module.module'].search([('name', 'in', ['dms', 'bgg_documents_dms'])]).button_immediate_install()
```

bgg_dms and bgg_dms_project install with it. Takes a few minutes.

## 2. Copy Documents into DMS

```python
env['bgg.documents.dms']._convert(commit=True)
```

Saved every 200 records; if the shell is cut, run it again (it continues).
Expected (staging, October 2026): about 2,850 folders, 6,300 files,
2,358 projects linked.

## 3. Check

```python
exec(open('/home/odoo/src/user/tools/ee_exit/ee_uninstall.py').read())
ee_check(env)
```

Compare with the reviewed check of 2026-10-23: "Other modules that would go
with them: none ✅", same records kept / deleted, counts as expected.

## 4. Uninstall Enterprise

Long (tens of minutes); run it in the background so a closed browser does
not stop it:

```bash
cat > ~/ee_run.py <<'EOF'
exec(open('/home/odoo/src/user/tools/ee_exit/ee_uninstall.py').read())
ee_uninstall(env, confirm=env.cr.dbname)
EOF
nohup odoo-bin shell --no-http < ~/ee_run.py > ~/ee_exit_uninstall.log 2>&1 &
tail -f ~/ee_exit_uninstall.log
```

(`Ctrl+C` stops `tail` only.) If it stops (memory, timeout), run the
`nohup` line again: it continues with the modules still installed and keeps
the counts saved before the first run.

At the end of the log: "WHAT MUST SURVIVE: before -> after", all ✅, and
"Enterprise modules still installed: none ✅".

Files kept in `~/ee_exit/<database>/`: `counts_before.json`,
`expected_losses.json`, `counts_after.json`, `whatsapp.json` (Meta account
ids and the 17 templates, without tokens). Download `whatsapp.json`.

## 5. Look at it

Log in and check: Sales (orders, "Créer Tâches SSS", "Tâches" button),
CRM, Calendar (RDV fields), Project (admin and SSS projects, Documents
button), Documents (DMS: Finance by company, project folders, search
"S00466"), Invoicing, Contacts, Employees, our dashboards (AMSS, call
center, commercial, commissions).

## 6. Backup for the Community server

Odoo.sh → the branch → Backups → download a dump **with filestore**. This
is what is restored on the VPS (Odoo 19 Community + OCA modules, then
bgg_booking with OCA resource_booking).

## Go-live differences

- Fix the data issues of `ee_exit_data_issues.md` on production first.
- Freeze production (users out), take the final copy, run steps 1-6 on
  it. `ee_uninstall` needs `go_live=True` on a database that is not
  neutralized.
- Knowledge: moved by then, or its articles are lost (see
  `ee_exit_module_plan.md`).
