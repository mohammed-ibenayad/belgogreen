# Enterprise exit: go-live plan

What changes on the day production moves from Odoo.sh (Enterprise) to the
Community server: the settings to change (and how), what to tell the team
and the customers, before, during and after. The technical steps are in
[ee_exit_runbook.md](ee_exit_runbook.md) and
[deploy/vps/README.md](../deploy/vps/README.md); the decisions still open
are in [ee_exit_open_decisions.md](ee_exit_open_decisions.md).

## Production today (2026-10-31)

| | Value |
|---|---|
| Odoo address (`web.base.url`) | `https://belgogreen.odoo.com` |
| Website | one, "BelGoGreen", on `https://belgogreen.odoo.com` (customer pages: quotes, invoices, `/my`) |
| Email domains in Odoo | `belgogreen.odoo.com`, `naturisol.odoo.com` (catchall, bounce, notifications) |
| Companies and their email | AMSS MANAGEMENT SRL: info@belgogreen.be · BelGoGreen SASU: compta@belgogreen.fr · NATUR'ISOL SRL: contact@naturisol.be |
| Open quotes | 141 draft, 91 sent; still valid: 5 |
| Unpaid customer invoices | 64 (sent with a payment link) |
| After go-live | Odoo.sh and Enterprise kept one year, one or two users: an archive |

Every link and reply address sent so far names `belgogreen.odoo.com`.

## The settings to change

**Set by the restore** (`restore_odoosh.sh`, repeatable, nothing to remember):

| Setting | New value | How |
|---|---|---|
| `web.base.url` | the new address (`BASE_URL`), frozen | script |
| Website address | the new address | script (only the `*.odoo.com` one) |
| `report.url` | inside the container (PDFs) | script |
| Database identity | new; Enterprise code removed | script |
| Email domains | the companies' domains | script, `MAIL_DOMAINS="belgogreen.odoo.com=… naturisol.odoo.com=…"` (#17) |

Restore command at go-live:

```bash
BASE_URL=https://<new address> MAIL_DOMAINS="belgogreen.odoo.com=<domain> naturisol.odoo.com=<domain>" \
    bash addons/belgogreen/deploy/vps/restore_odoosh.sh restore/production.zip restore/ee_exit.tgz
```

**Set by hand after the restore** (they hold passwords or depend on the
provider), in Odoo with the developer mode:

| Setting | Where | Notes |
|---|---|---|
| Third email domain (BelGoGreen SASU, `belgogreen.fr`) | Settings → Technical → Email Domains, then the company's email domain | only two exist today |
| Outgoing mail server | Settings → Technical → Outgoing Mail Servers | the provider's SMTP (#17); one per domain if the provider requires it ("FROM filtering") |
| Replies to Odoo (catchall) | Settings → Technical → Incoming Mail Servers, or a forward at the provider | `catchall@<domain>` must reach Odoo |
| Scheduled jobs | Settings → Technical → Scheduled Actions | a neutralized dump has them off: switch on the ones in use (#8) |
| Online payment | Invoicing → Configuration → Payment Providers | a neutralized dump disables them; live keys again, and the provider's webhook URL changed to the new address in the provider's own dashboard |
| Calendar sync (Google / Outlook) | the Google / Microsoft console | the allowed redirect address changes to the new one |
| SMS | Settings → SMS | check a test SMS: the credits belong to the IAP account in the database |

To check before go-live, on production (read only): what else names the
old address or depends on it.

```bash
psql -c "SELECT name, code, state FROM payment_provider WHERE state <> 'disabled';"
psql -c "SELECT key, value FROM ir_config_parameter WHERE key LIKE 'google%' OR key LIKE 'microsoft%' OR key LIKE '%calendar%';"
psql -c "SELECT 'mail template' AS what, id FROM mail_template WHERE body_html::text LIKE '%belgogreen.odoo.com%' UNION ALL SELECT 'view', id FROM ir_ui_view WHERE arch_db::text LIKE '%belgogreen.odoo.com%' UNION ALL SELECT 'url action', id FROM ir_act_url WHERE url LIKE '%belgogreen.odoo.com%';"
psql -c "SELECT name, smtp_host, from_filter, active FROM ir_mail_server; SELECT name, server, active FROM fetchmail_server;"
```

**At the registrar** (whoever manages the DNS of the domains):

| Record | For |
|---|---|
| A `<new address>` → the VPS's IP | the Odoo address (#18); then nginx and HTTPS on the server |
| SPF, DKIM, DMARC for belgogreen.be, belgogreen.fr, naturisol.be | emails from Odoo not taken for spam; given by the email provider; can take a day to spread: do it early |

**On the old Odoo.sh** (the day of the switch):

| Action | Why |
|---|---|
| Switch off Online Signature (Sales → Settings, each company) | no quote signed on the old Odoo after go-live (online payment is not used: no payment provider) |
| Resend the quotes still signable from the new Odoo | the customer gets a link to the new Odoo (count: open decision #16) |
| Redirect module, only if many quotes are still signable (#16) | old customer links open the same page on the new Odoo |
| Switch off outgoing mail servers and scheduled jobs | no reminder, follow-up or WhatsApp to customers from the old Odoo |
| Keep one or two users, archive the others | the one-year Enterprise subscription |
| Record nothing new | an archive; replies to old emails still arrive there (#16: forward them to a mailbox) |

## Communication

**Before (the week before)**

| Who | What |
|---|---|
| Team | The date and the freeze window (no Odoo use from the final copy to the switch, about half a day). The new address; bookmarks and the mobile app to change. Passwords stay the same. |
| Team | What changes on screen: the app menu, "Prise de RDV" (call centre and commercials, menus "Call Center" and "RDV Commercial"), Documents (DMS), the SSS task form. A short demo on the staging copy. |
| Call centre | During the freeze: note the RDVs on paper or in a shared sheet, enter them after the switch. |
| Accounting | The Enterprise accounting reports (VAT, follow-ups, assets, bank sync, CODA) stay in the old Odoo, consultable one year; bank import on the new one to settle (open decisions, general). |
| Customers | The quotes still signable are sent again from the new Odoo (new link). Old links still open the old Odoo, read only. |

**During (the day)**

| Who | What |
|---|---|
| Team | "Odoo is closed from … to …" at the start; "Odoo is open at <new address>" at the end. |

**After (first week)**

| Who | What |
|---|---|
| Team | One contact for problems; screenshots and the record's address. Daily check of the emails sent and received, the scheduled jobs and the payments. |
| Customers | Emails now come from the companies' own domains (`@belgogreen.be`, `@belgogreen.fr`, `@naturisol.be`) instead of `@belgogreen.odoo.com`. No action needed from them. |
| Old Odoo users | It is an archive: look, do not record. |

## Timeline

| When | What | Who |
|---|---|---|
| Now | Order the VPS (4 vCPU, 16 GB, 200 GB, #10); choose the new address (#18), the email provider and the domains (#17); off-server backups (#9) | business |
| T-3 days | Server installed, trial restore of a fresh copy, checks | IT |
| T-2 days | DNS: A record, SPF/DKIM/DMARC; email provider set up; redirect module tested on a staging copy | IT, whoever holds the DNS |
| T-1 day | Business sign-off of the staging copy (Phase 7); open decisions answered (Knowledge, WhatsApp, #14, #15) | business |
| T0 | Freeze; final copy and Enterprise exit (runbook, "Go-live"); dump; restore with `BASE_URL` and `MAIL_DOMAINS`; settings by hand; checks; old Odoo: redirect, mail and jobs off; open | IT |
| T+1 to T+7 | Follow-up of emails, jobs, payments; questions of the team | IT, business |
