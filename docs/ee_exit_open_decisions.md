# Enterprise exit: open decisions

Decisions left open on purpose, to settle before go-live. Each one has a
ready answer to give to Claude.

## Documents (OCA dms)

| # | Status | Question | Context | Options |
|---|--------|----------|---------|---------|
| 1 | ☐ Open | Archive the identical duplicate files? | The conversion copied every Enterprise document. The same file sometimes exists twice in one folder (e.g. a task attachment that was also filed in Documents), so DMS shows it twice. | **Archive the copies:** same folder and same content (checksum); the oldest stays, the others are archived, not deleted (they can be restored). **Keep as is.** |
| 2 | ☐ Open | Limit the "RH" folder to HR users? | The employee folders (with a "Contrat" / "Fiche de paie" sub-folder) are grouped under "RH". Each employee folder keeps the access it had in Enterprise (the users who had access there); "RH" itself is open to the users of those folders. | **Limit to HR:** give the users or Odoo group who may see RH. **Keep as is:** Enterprise access, folder by folder. |

## WhatsApp welcome messages

| # | Status | Question | Context | Options |
|---|--------|----------|---------|---------|
| 3 | ☐ Waiting (decided 2026-10-23: wait for OCA) | How to send the welcome WhatsApp on Community? | 8 active automation rules (20-27) send an approved WhatsApp template when a sale order is confirmed, one per company (Belgogreen, Naturisol) and payment term. They use Enterprise WhatsApp and stop when it is uninstalled. OCA `mail_gateway_whatsapp` is not released for 19.0: migration in OCA/mail PR #203 (open, not reviewed, template sending untested). | **Check again before go-live.** If released: install it and rebuild the 8 rules on it. If not: a small own module sending the templates through Meta's WhatsApp Cloud API (outbound only, same Meta account and templates), or the unreleased OCA branch. Until then, no automatic welcome message after go-live. |

## Sale order ↔ SSS project

| # | Status | Question | Context | Options |
|---|--------|----------|---------|---------|
| 4 | ☐ Open | Show the SSS project on its order, and the order on the SSS project? | On Community the SSS project is linked to its order by our own field (`x_sss_sale_order_id`, set by "Créer Tâches SSS"). The order's "Tâches" button already opens the tasks of both projects (admin and SSS), but the standard "Projets" button only finds the admin project (linked through the order line), and the SSS project form does not show its order. | **Add both** (small change in bgg_custom_dev): the SSS project in the order's "Projets" button, and a "Bon de commande" field with a link on the SSS project. **Keep as is:** reach the SSS tasks through "Tâches". |

## Booking and go-live

| # | Status | Question | Context | Options |
|---|--------|----------|---------|---------|
| 7 | ☐ Open | Do customers book themselves (public booking page)? | Enterprise Appointments has public pages (`/appointment/...`) anyone can open from the website, an ad or a signature. OCA `resource_booking` has none: a booking is started by a staff member, the customer then picks the time through a personal link. "Prise de RDV" covers the call centre and the commercials. | **Not used:** nothing to do. **Used:** a public page in bgg_booking (e.g. `/rendez-vous/<type>`) with the same free times, calendar and questionnaire, reCAPTCHA, duplicate check, choice of the public types; to build before go-live so the links keep working. |
| 8 | ☐ Open | Where to run the final pass at go-live? | `ee_uninstall` refuses a database that is not neutralized unless `go_live=True`. A staging copy is neutralized (no emails, no scheduled jobs). | **Staging copy:** production stays untouched as a fallback; on the Community server, switch the outgoing mail server and scheduled jobs back on after the restore. **Production itself** after a manual Odoo.sh backup (fallback: that backup), with `go_live=True`. |

## Community server

| # | Status | Question | Context | Options |
|---|--------|----------|---------|---------|
| 9 | ☐ Open | Where does the off-server backup of the filestore go? | The filestore is 31 GB (47,541 files, October 2026). `backup.sh` keeps nightly database dumps on the server; a copy of the filestore on the same disk would need another 31 GB the server does not have and would not survive a disk failure. None of the other instances on the server is backed up either. | **Hostinger VPS backups / snapshots** (whole server, nothing to set up). **Cloud storage** (Google Drive, S3, Backblaze B2) through rclone: `FILESTORE_BACKUP_DIR` in the cron line, and the database dumps copied there too. |
| 10 | ☐ Open | Which server for production? | Test server: 2 vCPU, 7.8 GB RAM (+4 GB swap), 96 GB disk, shared with three other Odoo instances and other apps. BelGoGreen alone: 34 GB of data (31 GB of files, growing), about 60 internal users, heavy dashboards. After the restore and the zip removed: about 35 GB free. | **Bigger plan** for this server (more disk and vCPU). **A dedicated VPS** for BelGoGreen (e.g. 4 vCPU, 16 GB, 200 GB), same Docker setup. |

## Rehearsal on bsi-staging (2026-10-30)

| # | Status | Question | Context | Options |
|---|--------|----------|---------|---------|
| 11 | ☐ Open | What to do with the 3 saved filters "Mes tâches" (ids 211, 212, 213, on tasks)? | Three users' copies of the same favorite: my tasks of today and later by **planned start** (`planned_date_begin`, Enterprise Planning). The field is removed with the uninstall and has no Community equivalent, so `ee_cleanup` cannot rename it: `ee_final_check` shows them ❌ ("removed field"). | **Rewrite on the deadline:** `["&", ("user_ids", "in", uid), ("date_deadline", ">=", "today")]` (my tasks due today or later). **Delete them:** users make their own favorite again. |
| 12 | ☐ Open | Knowledge: move the 227 articles, or let them go? | `ee_check` (Phase 3) lists them under "NOT MOVED YET": the uninstall deletes them. `keep=('knowledge',)` leaves an Enterprise module installed, so `ee_final_check` fails: not an option for the Community server. Rehearsal: let them go (production still has them). | **Move them first:** a script that copies each article (title, text, hierarchy) into DMS (e.g. an HTML or PDF file per article under a "Knowledge" folder), run before the uninstall at go-live. **Let them go:** export by hand what is worth keeping. |

| 13 | ☐ To discuss | Does the business accept the expected losses of the counts? | `ee_check` (Gate A, 2026-10-30), "WHAT MUST SURVIVE": Contacts -1 ("VAT Revenue Services"; "Collection Center - Advance Payment Service" is kept, in use), Projects -1 and SSS projects -1 (the empty "Field Service" project), Products -2 ("Booking Fees", "Field Service"), Messages -3 (chatter of those records), Automation rules -5 (on the removed models; the log names 1 "Add conjoint as Contact", 2 "Update Contact Info", 9 "Update Appointment Title", 15 "Set Partner On Behalf", all on appointment answers; the 5th is not named). Explained in [ee_exit_runbook.md](ee_exit_runbook.md), Phase 4. | **To get the exact list before the discussion** (on a copy before the uninstall): the 5 rules, `SELECT a.id, COALESCE(a.name->>'fr_BE', a.name->>'en_US'), a.active, m.model FROM base_automation a JOIN ir_model m ON m.id = a.model_id WHERE m.model LIKE 'appointment%' OR m.model LIKE 'knowledge%' OR m.model LIKE 'documents%' OR m.model LIKE 'whatsapp%' OR m.model LIKE 'sale.commission%'`; the 3 messages, `mail_message` on the res.partner "VAT Revenue Services" and the project.project "Field Service". Then: **accept**, or say which rule must be rebuilt on Community (what it did on the questionnaire). |

## Uninstall rehearsal on bsi-staging (2026-10-23)

| # | Status | Point | Context | Next step |
|---|--------|-------|---------|-----------|
| 5 | ☐ Later | 6 calendar events (RDVs with a type) lost in the rehearsal | They were linked to a record of an Enterprise model; Odoo deletes such events with the model. Lost on bsi-staging only (production still has them). The script now empties the link first and keeps the events (commit "keep calendar events linked to a removed model"). | Find which model on production (`SELECT m.model, count(*) FROM calendar_event e JOIN ir_model m ON m.id = e.res_model_id GROUP BY 1`), then confirm in a fresh rehearsal that "Calendar events" stays ✅. |
| 6 | ☐ Later | Users who lost Internal User (e.g. the call centre users) | Their rights came through Enterprise groups deleted at uninstall (Odoo 19 gives Internal User through other groups). On bsi-staging: restored by hand (Internal User). The script now gives users directly the rights they would lose, and counts active internal users. | In a fresh rehearsal: "Internal users (active)" stays ✅; check a call centre user and a commercial keep their menus. (Restore of 2026-10-24 on the server: all 44 active users can log in, after the fix by hand on staging.) |

## Notes

- "My Company" (not an active company) still owns 5 Finance sub-folders
  ("Achats/Banque/Divers/Espèces/Ventes - My Company"). Nobody can select
  that company, so they are hidden from everyone, as in Enterprise. If they
  hold files to keep, make them shared (clear "Société du dossier") or move
  them to a real company; if empty, delete them.

## General (still to decide)

- Bank(s) to connect on the Community server (bank statement import / sync).
- Accountant scope: what the accountant still needs from Odoo once the
  Accounting app is dropped.
- Go-live window (the date of the final Odoo.sh backup and the switch).
