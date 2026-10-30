# Enterprise exit: migration guide

From a **fresh copy of production on Odoo.sh staging** to a database
**without Enterprise, ready to dump** and restore on the Community server.
Every step can be redone from the start: take a new copy and follow the
guide again.

What each step moves, and which module does it, is in
[ee_exit_inventory.md](ee_exit_inventory.md). Decisions still open are in
[ee_exit_open_decisions.md](ee_exit_open_decisions.md).

## Overview

| Phase | What | Where | Gate (must pass before going on) |
|---|---|---|---|
| 0 | Prepare production and the code | production, GitHub | checklist below |
| 1 | Fresh production copy, our migrations run | Odoo.sh build | build green, migration lines in the log |
| 2 | Copy Documents into DMS | shell | counts of the copy |
| 3 | Gate A: everything moved? | shell | `ee_preflight(env)`: no ❌ · `ee_check(env)`: as the reference |
| 4 | Uninstall Enterprise | shell (background) | "All counts kept ✅", "Enterprise modules still installed: none ✅" |
| 5 | Community modules (look, booking) | Apps / shell | installs without error |
| 6 | Gate B: ready for the dump? | shell | `ee_final_check(env)`: no ❌ |
| 7 | Look at it, as each kind of user | browser | checklist below |
| 8 | Dump with filestore, and `ee_exit.tgz` | Odoo.sh | files downloaded |
| 9 | Restore on the Community server | VPS | `ee_final_check(env)` again: no ❌ |

**The script.** All the checks are in `tools/ee_exit/ee_uninstall.py`, an
Odoo shell script (not a module). Load it in each new shell with:

```python
exec(open('/home/odoo/src/user/tools/ee_exit/ee_uninstall.py').read())
```

| Function | Changes data? | What it does |
|---|---|---|
| `ee_preflight(env)` | no | Gate A. Our modules migrated; RDV type/status/answers, RDV type commercials, SSS flags, commission plans and Documents are in our own fields and modules; what goes with Studio. |
| `ee_check(env)` | no | What the uninstall will remove: modules in batches, other modules that would go with them (must be none), records kept because still in use, conditions on removed fields, values that disappear, counts. |
| `ee_uninstall(env, confirm=<db>)` | **yes** | Saves the counts, saves WhatsApp, keeps what is in use and the users' rights, uninstalls batch by batch, cleans up, compares the counts before/after. |
| `ee_cleanup(env)` | yes (safe) | Retries what a lock kept the uninstall from removing, removed view types, conditions, Studio icons. Run again whenever a gate says so. |
| `ee_blockers(env)` | no | Other connections holding locks (when the uninstall reports lock timeouts). |
| `ee_final_check(env)` | no | Gate B. No Enterprise left, Community modules installed, screens and users OK, booking set up, counts still those before the uninstall. |

Marks in the reports: ✅ good · ❌ must be fixed before going on · ⚠️ known,
look at it once (e.g. a Studio field nobody uses) · – not on this database.

**Shells.** Start every shell step in a **new** shell
(`odoo-bin shell --no-http`): a shell left open loses its database
connection. Long steps run in the background with `nohup` so a closed
browser does not stop them.

## Phase 0. Before you start

On **production** (the data carries over with the copy):

- [ ] Data issues of [ee_exit_data_issues.md](ee_exit_data_issues.md) fixed
      (call-centre contacts, bookable staff, booking rights).
- [ ] Open decisions answered, or knowingly left for later
      (duplicates, RH access, SSS links, Knowledge, WhatsApp).
- [ ] **No new Studio change left out.** Studio changes are lost with
      Studio unless `bgg_custom_dev` rebuilds them. On production (read
      only), list the Studio views still active:

      ```bash
      psql -c "SELECT v.id, p.name AS screen, v.model, v.write_date::date, u.login FROM ir_ui_view v JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id LEFT JOIN ir_ui_view p ON p.id = v.inherit_id LEFT JOIN res_users u ON u.id = v.write_uid WHERE d.module = 'studio_customization' AND v.active ORDER BY v.write_date DESC;"
      ```

      Each one must be in the inventory (section 4: rebuilt, or left on
      purpose). A new one (e.g. the sellable products list made on
      2026-10-21, found in the rehearsal of 2026-10-30): rebuild it in
      `bgg_custom_dev` with a migration that switches it off, before the
      copy. Phase 3 fails on it otherwise. Same for new Studio fields,
      server actions and automation rules (Phase 3, Studio section).
- [ ] Knowledge: decided. Its 227 articles are **deleted** by the uninstall
      unless they were moved first.

In **GitHub**:

- [ ] `bgg_ee_exit` merged into the branch you build (e.g. `bsi-staging`).
      It carries our modules at the versions with the migrations, the OCA
      modules (`dms`, `resource_booking`, `web_calendar_slot_duration`,
      `web_responsive`) and the script.

## Phase 1. Fresh production copy

1. Odoo.sh → the staging branch (e.g. `bsi-staging`) → **Rebuild**
   ("fresh copy of production"). Or, to keep the current staging database,
   create a new branch from `bsi-staging` in GitHub (e.g.
   `ee-exit-rehearsal`) and drag it into **Staging**.

   ⚠️ Do not use the "Reconstruire le Staging" button of
   `bgg_staging_rebuild` for this: its refresh strategy puts the staging
   branch back on production's code, without `bgg_ee_exit`.

2. The build copies production (neutralized: no emails, no scheduled
   jobs) and updates the modules whose version changed. Our migrations run
   then:

   | Module | Migration | Moves |
   |---|---|---|
   | bgg_custom_dev | 19.0.2.0.0 | Appointments → own RDV fields (type, status, answers), Field Service flag → SSS flag; installs the bridge `bgg_custom_dev_ee` |
   | bgg_custom_dev | 19.0.2.1.0 | Studio → module (fields kept, views rebuilt, Studio views switched off, filters repointed, SSS projects linked to their orders, AMSS ADMIN group adopted) |
   | bgg_custom_dev | 19.0.2.2.0 | Appointment staff → RDV type commercials |
   | bgg_custom_dev | 19.0.2.3.0 | Studio → module: the sellable products list (Studio view switched off); roles made by hand adopted as module groups (Administrateur, Directeur Commercial, Responsable Equipe Commercial, Technicien); the 4 RDV access rules made by hand adopted, two rewritten without ids |
   | belgogreen_sales_commission | 19.0.1.0.0 | Enterprise commission plans → own plans (same ids) |

3. **Gate.** The build is green. In its log (Odoo.sh → build → Logs →
   `odoo.log`, search "copied"), these lines appear with their counts:
   - `bgg_custom_dev: copied … RDV type(s), RDV type/status on … event(s), questionnaire answers on … event(s), SSS flag on … project(s)`
   - `bgg_custom_dev: Enterprise bridge bgg_custom_dev_ee marked for installation`
   - `bgg_custom_dev: … Studio view(s) switched off`, `… SSS project(s) linked to their sale order`
   - `bgg_custom_dev: … commercial(s) copied to the RDV types from the appointment types`
   - `bgg_custom_dev: 1 Studio view(s) switched off` a second time (19.0.2.3.0,
     the products list; absent on a database where Studio is already gone)
   - `bgg_custom_dev: group 'Administrateur' (id 57) adopted as group_administrateur`,
     and the same for Directeur Commercial, Responsable Equipe Commercial,
     Technicien (19.0.2.3.0)
   - `bgg_custom_dev: access rule '[ADD] …' (id …) adopted as rule_calendar_event_…`
     (4 rules; 2 more on activities in 19.0.2.3.2), and `access rule rule_calendar_event_call_center_types now …`,
     `… call_center_public now …` (19.0.2.3.0)
   - `bgg_custom_dev: … SSS stage(s) created on the SSS projects that missed them`
     (older SSS projects made in Field Service had no "SSS: À faire"),
   - `bgg_custom_dev: … SSS task(s) moved from a 'Nouveau' stage to 'SSS: À faire'`,
     `… stage(s) taken off the SSS projects`, `… unused stage(s) deleted`
     (19.0.2.3.0 and 19.0.2.3.1; on the copy of 2026-10-30: about 200
     tasks, 18 "Nouveau" and 36 Planifié / En cours / Terminé / Annulé
     stages; 19.0.2.3.0 alone left 190 tasks in projects without
     "SSS: À faire"). A warning
     `stage … still holds … SSS task(s)` names a stage left as is: look at it.
   - `belgogreen_sales_commission: copied … commission plan(s) and … plan assignment(s)`

   The counts are checked exactly in Phase 3 (`ee_preflight`).

   Red build: stop, send the log. Nothing is lost, the copy is thrown away.

## Phase 2. Copy Documents into DMS

1. Install DMS (new shell):

   ```python
   env['ir.module.module'].search([('name', 'in', ['dms', 'bgg_documents_dms'])]).button_immediate_install()
   ```

   `bgg_dms` and `bgg_dms_project` install with it. A few minutes.

2. Copy (new shell):

   ```python
   env['bgg.documents.dms']._convert(commit=True)
   ```

   Saved every 200 records. If the shell is cut, run it again: it carries
   on with what is not copied yet.

3. **Gate.** It ends with its counts. Staging, October 2026: about 2,850
   folders, 6,300 files, 2,358 projects linked to their folder.

## Phase 3. Gate A: everything moved?

New shell:

```python
exec(open('/home/odoo/src/user/tools/ee_exit/ee_uninstall.py').read())
ee_preflight(env)
```

Must end with **"Ready for the uninstall ✅"**. What it checks:

| Section | ❌ when |
|---|---|
| Modules | `bgg_custom_dev`, `belgogreen_sales_commission`, the bridge or the DMS modules not installed, or installed at an older version than the code (migration not run); a module left half-way. ⚠️: a group made by hand that no module declares (add it to `bgg_custom_dev/security/groups.xml` and its adoption to a migration) |
| RDVs | an RDV whose own type or status differs from the Appointments one; answers without the questionnaire summary; an appointment type without its RDV type; staff missing from the RDV type commercials |
| SSS projects | a Field Service project not flagged SSS (⚠️: SSS projects without their order, open decision #4) |
| Commissions | a commission, role or plan assignment on a plan that is not ours |
| Documents | a folder or file not copied to DMS (links, shortcuts and spreadsheets are not copied on purpose); a project with a Documents folder but no DMS folder |
| Studio | an active Studio view not rebuilt in `bgg_custom_dev` and not left on purpose ("Active Studio views not rebuilt": a screen change lost with Studio; it names the screen, the date and who made it). ⚠️ only: Studio fields with data, Studio models, active Studio actions and automation rules that go with Studio |

Then:

```python
ee_check(env)
```

Compare with the reviewed check of 2026-10-23:
- "OTHER MODULES THAT WOULD GO WITH THEM: none ✅" (**required**:
  `ee_uninstall` refuses otherwise),
- the same records kept as still in use,
- "ROWS LINKED TO A REMOVED MODEL": the calendar events are "KEPT",
- "NOT MOVED YET": Knowledge and WhatsApp as decided in Phase 0.
- "VALUES IN THE REMOVED FIELDS OF KEPT MODELS": every Enterprise field of
  a kept model (tasks, orders, invoices…) that holds data, with its count.
  These values are lost. Go through the list once: a field still used must
  be declared in `bgg_custom_dev` under the same name before the copy (its
  column then stays), as done for the planned start of tasks
  (`planned_date_begin`, lost in the rehearsal of 2026-10-30).

  Two of them are open decisions (#14, #15); check them on each new copy,
  before the uninstall (read only):

  ```bash
  # 14: tasks marked done in Field Service but still open
  psql -c "SELECT t.id, t.name, COALESCE(p.name->>'fr_BE', p.name->>'en_US') AS project, p.x_is_sss_project AS sss, t.state, COALESCE(s.name->>'fr_BE', s.name->>'en_US') AS stage, t.write_date::date AS last_change FROM project_task t LEFT JOIN project_project p ON p.id = t.project_id LEFT JOIN project_task_type s ON s.id = t.stage_id WHERE t.fsm_done AND t.state NOT IN ('1_done', '1_canceled') ORDER BY t.id;"
  # 15: the RDV booker, compared with what is kept (creator, attendees, pris à la place de)
  psql -c "SELECT count(*) AS with_booker, count(*) FILTER (WHERE e.appointment_booker_id = u.partner_id) AS booker_is_the_creator, count(*) FILTER (WHERE e.appointment_booker_id = e.x_studio_rendez_vous_pris_la_place_de) AS booker_is_pris_a_la_place_de, count(*) FILTER (WHERE e.appointment_booker_id IN (SELECT r.res_partner_id FROM calendar_event_res_partner_rel r WHERE r.calendar_event_id = e.id)) AS booker_is_an_attendee FROM calendar_event e LEFT JOIN res_users u ON u.id = e.create_uid WHERE e.appointment_booker_id IS NOT NULL;"
  ```

  2026-10-30: 5 tasks (2 leave counters without project, 3 recent SSS
  after-sales tasks); booker an attendee on 9,133 of 9,161 RDVs.

## Phase 4. Uninstall Enterprise

Tens of minutes. Run it in the background:

```bash
cat > ~/ee_run.py <<'EOF'
exec(open('/home/odoo/src/user/tools/ee_exit/ee_uninstall.py').read())
ee_uninstall(env, confirm=env.cr.dbname)
EOF
nohup odoo-bin shell --no-http < ~/ee_run.py > ~/ee_exit_uninstall.log 2>&1 &
tail -f ~/ee_exit_uninstall.log
```

(`Ctrl+C` stops `tail` only.) What it does, in order:

1. Saves the counts of what must survive (`counts_before.json`, once) and
   the WhatsApp accounts and 17 templates (`whatsapp.json`, without tokens);
   archives the 8 WhatsApp welcome rules.
2. Empties the link of calendar events to removed models (the events stay).
3. Gives users directly the rights they got through Enterprise groups
   (call centre users keep "Internal User").
4. Renames the replaced Enterprise fields in access rules, filters, menus
   and automation rules (e.g. `appointment_type_id` → `x_rdv_type_id`).
5. Protects the records Enterprise created that are still in use.
6. Uninstalls batch by batch. Stopped (memory, timeout)? Run the `nohup`
   line again: it carries on, and keeps the counts saved the first time.
7. `ee_cleanup`, then compares the counts.

**Gate.** At the end of the log:
- "WHAT MUST SURVIVE: before -> after": all ✅,
- "Enterprise modules still installed: none ✅",
- "All counts kept ✅".

**The "(-N expected)" in the counts.** A count may go down by the number
shown, and only by it: these are records the Enterprise apps created for
themselves, that no order, invoice, RDV or task uses, deleted with their
app. No business data is in them. On the copy of 2026-10-30:

| Count | Expected | What goes, and why it does not matter |
|---|---|---|
| Contacts | -1 | "VAT Revenue Services", a tax-office contact an Enterprise accounting module created; never used on an invoice or payment ("Collection Center - Advance Payment Service" is used: kept). |
| Projects | -1 | The empty "Field Service" project Field Service creates when installed (no task); the SSS projects are separate projects, all kept. |
| SSS projects | -1 | The same "Field Service" project: as a Field Service project it got the SSS flag in the migration. |
| Products | -2 | "Field Service" and "Booking Fees", the products of Field Service and of paid appointments; on no order or invoice. |
| Messages | -3 | The chatter messages of the records above (e.g. "Project created"). |
| Automation rules | -5 | The 5 rules on appointment answers: 1 "Add conjoint as Contact", 2 "Update Contact Info", 9 "Update Appointment Title", 13 "Set Clickable Customer Phone", 15 "Set Partner On Behalf", **all already inactive on production** (checked 2026-10-30). They work on the Appointments questionnaire, which goes; the questionnaire is now kept on the RDV itself (`x_rdv_answers`) and "pris à la place de" is set by bgg_custom_dev. |

Everything else (users, orders, invoices, payments, RDVs, tasks, DMS,
commissions…) must keep exactly its count: the line shows ❌ otherwise. The
numbers come from `ee_check` (Phase 3), which lists each record by name
under "RECORDS THE MODULES CREATED"; they are saved in
`expected_losses.json` and checked again after the restore.

Lock timeouts in the log ("could not obtain lock")? Run `ee_blockers(env)`
to see who holds them, then `ee_cleanup(env)` in a new shell.

Files in `~/ee_exit/<database>/`: `counts_before.json`,
`expected_losses.json`, `counts_after.json`, `whatsapp.json`.
**Download `whatsapp.json`** (needed to set WhatsApp up again).

## Phase 5. Community modules

1. Remove `bgg_staging_rebuild` if installed (not taken to the Community
   server):

   ```python
   m = env['ir.module.module'].search([('name', '=', 'bgg_staging_rebuild')])
   if m.state == 'installed':
       m.button_immediate_uninstall()
   ```

2. Install the OCA look and the booking (new shell):

   ```python
   env['ir.module.module'].update_list()
   env['ir.module.module'].search([('name', 'in', ['web_responsive', 'bgg_booking'])]).button_immediate_install()
   ```

   `resource_booking` and `web_calendar_slot_duration` install with
   `bgg_booking`. The installation also adopts the top-level menus
   "Call Center" and "RDV Commercial" made by hand (they opened the
   Enterprise booking pages): log `bgg_booking: menu … adopted, now opens
   Prise de RDV`; they now open "Prise de RDV". Its installation creates the booking types from the RDV
   types (Mon–Sat 9:00–21:00, 2 h, one resource per commercial), sets
   "Réservable par" (call-centre types for "Call Center", "par commercial"
   types for "Commercial") and gives "Prise de RDV" to those two roles.

3. Users who book but are in neither role (data issue #4): give them the
   "Prise de RDV (call center)" group (Settings → Users).

4. Apps screen at login instead of Discuss (`web_responsive`'s "Redirect to
   Home"), for the internal users without a Home Action:

   ```python
   env['res.users'].search([('share', '=', False), ('action_id', '=', False)]).write({'is_redirect_home': True})
   env.cr.commit()
   ```

   (Can also be done on the Community server after the restore.)

⚠️ On Odoo.sh the Apps screen still offers the Enterprise apps (their code
is always there). **Never click "Activer" on them.** On the Community
server they do not exist.

## Phase 6. Gate B: ready for the dump?

New shell:

```python
exec(open('/home/odoo/src/user/tools/ee_exit/ee_uninstall.py').read())
ee_final_check(env)
```

Must end with **"Ready for the dump ✅"**. What it checks:

| Section | ❌ when |
|---|---|
| Modules | an Enterprise module installed, or a module from the Enterprise folder; an installed module whose code is not on the server (e.g. an Odoo.sh theme, once restored elsewhere); records left by uninstalled modules; a module half-way; one of `bgg_custom_dev`, `belgogreen_sales_commission`, `dms`, `bgg_dms`, `bgg_dms_project`, `web_responsive`, `resource_booking`, `web_calendar_slot_duration`, `bgg_booking` missing or not at its code version; `bgg_staging_rebuild` installed |
| Screens and users | an app icon in Studio's format (black app menu); an action with a removed view type (gantt, map...); an active user who cannot log in (no user type) |
| Conditions | an access rule, filter, menu or automation rule still naming a replaced Enterprise field (`ee_cleanup` renames it) or a removed one (fix by hand) |
| Booking | no booking type, nobody can book (⚠️: a type without "Réservable par") |
| What must survive | a count lower than before the uninstall (minus the expected losses) |

Most ❌ of the "Screens" and "Conditions" sections are fixed by
`ee_cleanup(env)`; run `ee_final_check(env)` again after it. The same check
runs again on the Community server after the restore.

## Phase 7. Look at it

Reload with **Ctrl+F5** first. As **admin**:

- [ ] App menu (top left) opens with all apps and their icons.
- [ ] Sales: an order with its "Tâches" button (admin and SSS tasks),
      "Créer tâches SSS", commission fields; quotations list columns.
- [ ] CRM, Contacts (form and list columns).
- [ ] Calendar: an RDV with its type, status, questionnaire, "pris à la
      place de"; list columns.
- [ ] Project: an admin project and an SSS project, their tasks, the
      "Documents" button.
- [ ] An SSS task: client with its address and "Voir l'itinéraire" (opens
      the route in Google Maps), contact number, planned dates, allocated
      time, description.
- [ ] Documents (DMS): Finance per company (company switcher), project
      folders, search "S00466".
- [ ] Invoicing: invoices, payments.
- [ ] Dashboards: AMSS, Call Center, Suivi commercial; Commissions.

As a **call-centre user** (e.g. "Call Center Interne"; set a password on
staging):

- [ ] Logs in, sees their menus.
- [ ] "Prise de RDV": only the 2 call-centre types; month calendar with
      free days; booking one creates the RDV with type, status and
      questionnaire.

As a **commercial**:

- [ ] Logs in, sees their RDVs and the "par commercial" types.

## Phase 8. Dump

1. Odoo.sh → the branch → **Backups** → **Create Backup**. A row of the
   branch appears (the `main` rows are production's backups: not those).
2. Its download icon → **Neutralized** (rehearsal; "Exact" at go-live, see
   below) and **With filestore**. Odoo.sh notifies when it is ready.
3. Also download `~/ee_exit/` from the branch's shell
   (`tar czf ~/ee_exit.tgz -C ~ ee_exit`, then Editor → right-click →
   Download): the counts before the uninstall, for the check after the
   restore, and the WhatsApp templates. It is gone when Odoo.sh rebuilds
   the branch: take it right after the uninstall.

October 2026: a 27 GB zip (1 GB of SQL, 31 GB of files), about 50 minutes
to upload at 10 MB/s.

## Phase 9. Restore on the Community server

[deploy/vps/README.md](../deploy/vps/README.md): upload, `restore_odoosh.sh`
(loads, updates our modules, runs `ee_cleanup` and `ee_final_check` again),
domain, backups.

## Go-live: what changes

- Production is frozen (users out) from the final copy to the switch.
- `ee_uninstall` refuses a database that is not neutralized unless
  `go_live=True`. Where to run the final pass is decided with the go-live
  window:
  - **on a staging copy** (production stays untouched as a fallback): the
    dump is neutralized, so on the Community server the outgoing mail
    server and the scheduled jobs are switched back on after the restore;
  - **on production itself** after a manual Odoo.sh backup (the fallback is
    that backup): run with `ee_uninstall(env, confirm=..., go_live=True)`.
- WhatsApp and Knowledge as decided in Phase 0.
- Download `ee_exit.tgz` (Phase 8) before anything rebuilds the branch.
- The restore, the domain, emails and backups:
  [deploy/vps/README.md](../deploy/vps/README.md) (server size: open
  decision #10).

## Rehearsals

| Date | Database | Result |
|---|---|---|
| 2026-10-23 | bsi-staging | All counts kept except 6 calendar events (fixed since: links emptied first, open decision #5); users who lost "Internal User" (fixed since: rights kept, #6); 4 leftovers of lock timeouts removed by `ee_cleanup`; no Enterprise code left, 141 modules. After it: app icons in Studio's format (black app menu) and an access rule on `appointment_type_id`, both fixed in the script. |
| 2026-10-24 | bsi-staging dump → VPS (Docker) | Restore of the 2026-10-23 database: 27 GB zip, 144 modules, 31.2 GB / 47,541 files, about 10 minutes. `ee_final_check`: no Enterprise, all our modules at their code version, 44 users can log in, 4 booking types, 28 users can book; "Ready for the dump ✅". Found: automation rule 16 "Subscribe Admins to FSM Tasks" still filtered on the task's `is_fsm` (renamed since, and the final check now fails on such conditions); `ee_exit.tgz` not available (branch rebuilt since the uninstall). Two harmless load errors (`vector` extension of the Enterprise AI). |
| 2026-10-30 | bsi-staging (fresh copy of production, client repository) | First full run of this guide, Phases 1–6, both gates passed. Migrations: 14 commission plans, 7 RDV types (34,255 RDVs, 9,963 with answers), 907 SSS projects (897 with their order), 12 Studio views off, 301 RDV type commercials. DMS: 2,913 folders, 6,102 files, 2,421 projects linked, no error. Uninstall: no Enterprise left, all counts kept (expected losses only: open decision #13); two foreign-key errors on Documents rows during the uninstall, harmless (tables dropped right after, DMS counts unchanged). Booking: 4 types, 28 users can book. 44 users with the apps screen at login. `ee_final_check`: "Ready for the dump ✅". Found after it: the Studio view of the sellable products list (made 2026-10-21, active, not rebuilt; lost on this copy): rebuilt in `bgg_custom_dev` 19.0.2.3.0, and `ee_preflight` now fails on such a view. |
| 2026-10-30 (2nd run) | bsi-staging, recreated from bgg_ee_exit, fresh copy of production | Phases 1–6, both gates passed, with the fixes of the first run: products list rebuilt, groups, RDV and activity rules adopted with their production ids (rules 253 and 428 without ids), SSS stages cleaned (18 stages created on 9 projects, 190 tasks moved, 14 stages off the SSS projects, 6 deleted), planned start kept (5,217 tasks before and after). DMS: 2,913 folders, 6,103 files, 2,421 projects. Check A: no Studio view, group or rule left out; the menus adopted by bgg_booking at Phase 5. Uninstall: all counts kept. Check B: "Ready for the dump ✅". The 3 "Mes tâches" filters deleted again (saved on a Field Service screen, decision #11). |
| next | 2nd run dump → VPS | Phases 7–9: look at it, dump with filestore and `ee_exit.tgz`, restore on the server. |
