# Enterprise exit: open decisions

Decisions left open on purpose, to settle before go-live. Each one has a
ready answer to give to Claude.

## Documents (OCA dms)

| # | Status | Question | Context | Options |
|---|--------|----------|---------|---------|
| 1 | ☐ Open | Archive the identical duplicate files? | The conversion copied every Enterprise document. The same file sometimes exists twice in one folder (e.g. a task attachment that was also filed in Documents), so DMS shows it twice. | **Archive the copies:** same folder and same content (checksum); the oldest stays, the others are archived, not deleted (they can be restored). **Keep as is.** |
| 2 | ☐ Open | Limit the "RH" folder to HR users? | The employee folders (with a "Contrat" / "Fiche de paie" sub-folder) are grouped under "RH". Each employee folder keeps the access it had in Enterprise (the users who had access there); "RH" itself is open to the users of those folders. | **Limit to HR:** give the users or Odoo group who may see RH. **Keep as is:** Enterprise access, folder by folder. |

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
