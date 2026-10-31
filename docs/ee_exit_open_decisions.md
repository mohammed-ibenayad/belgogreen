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
| 11 | ☐ Check in the next run | The 3 saved filters "Mes tâches" (ids 211, 212, 213, on tasks) | Three users' copies of the same favorite: my tasks of today and later by **planned start** (`planned_date_begin`, Enterprise Planning). In the rehearsal of 2026-10-30 the field was dropped with Enterprise and the **filters were deleted** with it (gone from bsi-staging afterwards), which is why no check flagged them. `planned_date_begin` is now declared in bgg_custom_dev (column kept), so they should stay. | In the next run, after the uninstall: `SELECT id, name FROM ir_filters WHERE id IN (211,212,213)` returns the 3 filters. |
| 12 | ☐ Open | Knowledge: move the 227 articles, or let them go? | `ee_check` (Phase 3) lists them under "NOT MOVED YET": the uninstall deletes them. `keep=('knowledge',)` leaves an Enterprise module installed, so `ee_final_check` fails: not an option for the Community server. Rehearsal: let them go (production still has them). | **Move them first:** a script that copies each article (title, text, hierarchy) into DMS (e.g. an HTML or PDF file per article under a "Knowledge" folder), run before the uninstall at go-live. **Let them go:** export by hand what is worth keeping. |

| 13 | ☐ To discuss | Does the business accept the expected losses of the counts? | `ee_check` (Gate A, 2026-10-30), "WHAT MUST SURVIVE": Contacts -1 ("VAT Revenue Services"; "Collection Center - Advance Payment Service" is kept, in use), Projects -1 and SSS projects -1 (the empty "Field Service" project), Products -2 ("Booking Fees", "Field Service"), Messages -3 (chatter of those records), Automation rules -5: 1 "Add conjoint as Contact", 2 "Update Contact Info", 9 "Update Appointment Title", 13 "Set Clickable Customer Phone", 15 "Set Partner On Behalf", all on appointment answers and **all already inactive on production** (checked 2026-10-30). Explained in [ee_exit_runbook.md](ee_exit_runbook.md), Phase 4, and in the rehearsal report. | **Accept** (nothing in use is lost), or name what must be rebuilt on Community. |
| 14 | ☐ To decide | Close the tasks marked done in Field Service but still open? | `project.task.fsm_done` ("Task done", Field Service) goes with Enterprise. 3,440 tasks have it; all are closed (done or cancelled) except 5 still "in progress" (staging copy of 2026-10-30): 3020 "Vacances annuelles 20 jours total 2025" and 3021 "Jours fériés 2025" (no project, mario.greco; leave counters), 9478 "Clôtures" (S00711 - SSS - SECCI sophie, changed 2026-10-08), 11992 "SAV 2 / Non conforme - Différentiel" (S00531, 2026-10-27) and 12457 "REMISE AUX NORMES DES FUSIBLES" (S01144, 2026-10-28), the last three SSS, recent and assigned, so probably reopened for after-sales work. On Community they show as open. | **Leave them open** (likely: recent after-sales work and leave counters). **Close them** on production before the copy if they are finished. To list them: Phase 3 of the guide. |
| 15 | ☐ To decide | Keep the booker of the RDVs, and the signer of the invoices? | `calendar.event.appointment_booker_id` (Appointments: who booked) is set on 9,161 RDVs and goes with Appointments. The bookers are call-centre contacts (call marrakech 43, Call Center Casa 9, Call Center Digitrends 3…) and customers. On 9,133 of them (99.7 %) the booker is also an **attendee** of the RDV (kept); 57 are the RDV's creator, 1 the "pris à la place de"; about 28 are none of these. `account.move.signing_user` (1,301 invoices): the signatory printed by the Enterprise invoice reports. | **Let them go** (recommended for the booker: kept as an attendee). **Keep them:** declared in bgg_custom_dev under the same name before the copy (values kept). For the signer: ask accounting. To check them again: Phase 3 of the guide. |

## Uninstall rehearsal on bsi-staging (2026-10-23)

| # | Status | Point | Context | Next step |
|---|--------|-------|---------|-----------|
| 5 | ☐ Later | 6 calendar events (RDVs with a type) lost in the rehearsal | They were linked to a record of an Enterprise model; Odoo deletes such events with the model. Lost on bsi-staging only (production still has them). The script now empties the link first and keeps the events (commit "keep calendar events linked to a removed model"). | Find which model on production (`SELECT m.model, count(*) FROM calendar_event e JOIN ir_model m ON m.id = e.res_model_id GROUP BY 1`), then confirm in a fresh rehearsal that "Calendar events" stays ✅. |
| 6 | ☐ Later | Users who lost Internal User (e.g. the call centre users) | Their rights came through Enterprise groups deleted at uninstall (Odoo 19 gives Internal User through other groups). On bsi-staging: restored by hand (Internal User). The script now gives users directly the rights they would lose, and counts active internal users. | In a fresh rehearsal: "Internal users (active)" stays ✅; check a call centre user and a commercial keep their menus. (Restore of 2026-10-24 on the server: all 44 active users can log in, after the fix by hand on staging.) |

## Go-live: addresses, emails, the old Odoo (2026-10-31)

Production today: `web.base.url` = `https://belgogreen.odoo.com`, one
website "BelGoGreen" on `https://belgogreen.odoo.com` (company AMSS
MANAGEMENT SRL), email domains `belgogreen.odoo.com` and
`naturisol.odoo.com` (catchall, bounce, notifications). 64 unpaid customer
invoices; 232 open quotes, 5 still valid. Plan: [ee_exit_golive.md](ee_exit_golive.md). Odoo.sh and Enterprise are kept one year with one or two users.

| # | Status | Question | Context | Options |
|---|--------|----------|---------|---------|
| 16 | ☐ Leaning: no redirect | What happens to the links sent before go-live (open quotes, unpaid invoices)? | Every link sent so far is `https://belgogreen.odoo.com/my/...?access_token=...`; the old Odoo stays one year, so those links keep opening it. Production, 2026-10-31: **no online payment** (no active payment provider, 0 online payments in 90 days); **online signature on** for the 3 companies and used a lot (286 quotes signed online in 90 days); 5 open quotes still valid. A quote signed on the old Odoo after go-live is not in the new one. Email replies go to the old Odoo with or without a redirect. | **No redirect** (no code): on the old Odoo switch off Online Signature (Sales settings, each company), outgoing emails and scheduled jobs; resend the quotes still signable from the new Odoo at go-live; an admin checks the old Odoo daily for messages and replies. **Redirect** (a small module on the old Odoo.sh): worth it if many quotes are still signable at go-live. To count them on the day: `SELECT count(*) FROM sale_order WHERE state IN ('draft','sent') AND require_signature AND signature IS NULL AND (validity_date IS NULL OR validity_date >= current_date);` |
| 17 | ☐ Open | Which email domains on the new server (the "3 domains": belgogreen.be, belgogreen.fr, naturisol.be, the emails of the 3 companies)? | On Odoo.sh, Odoo's mail server sends and receives for `belgogreen.odoo.com` and `naturisol.odoo.com`. On the new server: an email provider (Brevo, Mailgun, Microsoft 365 / Google…) for sending, the companies' own domains as email domains (one per company, e.g. belgogreen.be, naturisol.be, AMSS), each validated with SPF / DKIM / DMARC records, and replies (catchall) delivered to Odoo (forward to a mailbox read by Odoo). | To give: the 3 domains, the provider, who manages their DNS. |
| 18 | ☐ Open | Which address for the new Odoo? | One name, e.g. `erp.belgogreen.be`: an A record at the registrar to the VPS's IP, then nginx and the HTTPS certificate on the server (deploy/vps/README.md, section 5). | To give: the name, who has access to the DNS. |

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
