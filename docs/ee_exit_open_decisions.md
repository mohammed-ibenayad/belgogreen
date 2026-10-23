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

## Uninstall rehearsal on bsi-staging (2026-10-23)

| # | Status | Point | Context | Next step |
|---|--------|-------|---------|-----------|
| 5 | ☐ Later | 6 calendar events (RDVs with a type) lost in the rehearsal | They were linked to a record of an Enterprise model; Odoo deletes such events with the model. Lost on bsi-staging only (production still has them). The script now empties the link first and keeps the events (commit "keep calendar events linked to a removed model"). | Find which model on production (`SELECT m.model, count(*) FROM calendar_event e JOIN ir_model m ON m.id = e.res_model_id GROUP BY 1`), then confirm in a fresh rehearsal that "Calendar events" stays ✅. |

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
