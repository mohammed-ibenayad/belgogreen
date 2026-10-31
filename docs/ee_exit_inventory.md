# Enterprise exit: what we took from Enterprise

Everything BelGoGreen used in Odoo Enterprise and keeps on Odoo Community:
what replaces it, in which module, and which migration moves the data. The
steps to run are in [ee_exit_runbook.md](ee_exit_runbook.md); the fate of
each of the 129 Enterprise modules (moved, dropped, waiting) is in
[ee_exit_module_plan.md](ee_exit_module_plan.md).

## Summary

| Enterprise | Replaced by | Module | Data moved by |
|---|---|---|---|
| Appointments: RDV type, status, questionnaire on events | Own RDV fields and RDV types | bgg_custom_dev | migration 19.0.2.0.0 |
| Appointments: staff per type | RDV type commercials | bgg_custom_dev | migration 19.0.2.2.0 |
| Appointments: booking pages used by the call centre | "Prise de RDV" on OCA `resource_booking` | bgg_booking | installation (types from the RDV types) |
| Field Service: "Field Service" projects, "Créer tâches SSS" | SSS flag and link to the order, plain projects and tasks | bgg_custom_dev | migrations 19.0.2.0.0, 19.0.2.1.0 |
| Odoo Studio: fields, views, actions, filters, group | Declared in code | bgg_custom_dev, belgogreen_sales_commission | migration 19.0.2.1.0 |
| Commissions (Enterprise `sale_commission` plans) | Own commission plans | belgogreen_sales_commission | migration 19.0.1.0.0 |
| Documents | OCA `dms` + company, projects | dms, bgg_dms, bgg_dms_project | bgg_documents_dms (one-off copy) |
| Enterprise home screen of apps | OCA `web_responsive` | web_responsive | – |
| Gantt / map views in window actions | Removed from the actions | – | `ee_cleanup` |
| Enterprise field names in rules, filters, menus, automations | Renamed to our fields | – | `ee_uninstall` (step 4) |

Temporary, removed with Enterprise: `bgg_custom_dev_ee` (keeps both sides
in sync until the uninstall) and `bgg_documents_dms` (the copy).

## 1. Appointments → bgg_custom_dev (data)

bgg_custom_dev no longer depends on Enterprise (19.0.2.0.0). Its business
rules (no-show workflow, commercial detection, call-centre attribution on
orders, Suivi Commercial / Call Center / AMSS dashboards, avis report)
read its own fields:

| Enterprise | Ours | Notes |
|---|---|---|
| `appointment.type` | `bgg.rdv.type` (name, code, sequence, active, commercials `user_ids`) | **same ids**, so stored ids and conditions stay valid; code = former `x_appointment_ref`; menu Calendar → Configuration → RDV types |
| `calendar.event.appointment_type_id` | `x_rdv_type_id` | |
| `calendar.event.appointment_status` | `x_rdv_status` | same values |
| `appointment.answer.input` (per event) | `x_rdv_answers` | text summary of the questionnaire |
| `appointment.type.staff_user_ids` | `bgg.rdv.type.user_ids` | 301 commercial links on staging |
| hard-coded ids (types 2/4/19/20, group 59) | RDV type codes, group found by name | |

The migration copies the data in SQL before the module loads; the bridge
`bgg_custom_dev_ee` keeps both sides in sync while Enterprise is still
installed (status both ways, questionnaire automations: spouse contact,
address, title, "pris à la place de").

Checked by `ee_preflight` (RDVs section) and counted by `ee_uninstall`:
"RDVs with an RDV type", "RDVs with answers", "RDV types".

## 2. Appointments booking → OCA resource_booking + bgg_booking

The booking pages the call centre used are replaced by **"Prise de RDV"**,
a form in the steps of those pages, on OCA `resource_booking`:

1. RDV type (only the types the user may book: "Réservable par"),
2. commercial, or "Voir toutes les disponibilités",
3. month calendar of the free days, free times of the chosen day (one
   button per free commercial), previous / next / next free day,
4. client (found by phone, last 8 digits, or created; empty fields
   filled), address and questionnaire in the Appointments order,
5. booked: open the RDV or book another one.

| Part | Where |
|---|---|
| Booking type ↔ RDV type, needs, single/multiple need, questions asked, opportunity created | `resource.booking.type`: `x_rdv_type_id`, `x_need_ids`, `x_need_multiple`, `x_ask_*`, `x_create_opportunity` |
| "Réservable par" (groups) | `resource.booking.type.x_group_ids`: call-centre types (code `-CNT`) for "Call Center", "par commercial" types (`-COM`) for "Commercial" |
| Questionnaire on the booking | `resource.booking`: address, `x_solar_since`, `x_is_owner`, `x_need_ids`, spouse, `x_sms_confirmation`, `x_on_behalf_id`, `x_comments` |
| Needs ("Besoin") | `bgg.rdv.need` |
| The meeting | RDV type, "Réservé" status, questionnaire summary, "pris à la place de", the commercial as organizer, Appointments-style title, CRM opportunity linked |
| Cancelling | the meeting stays as a cancelled RDV and frees the slot |
| Rights | group "Prise de RDV (call center)" (sees all bookings), added to the "Call Center" and "Commercial" roles at installation |
| Setup at installation | booking types from the RDV types, Mon–Sat 9:00–21:00, 2 h slots, one resource per commercial, no company (shared by the companies) |
| Screens | wizard `bgg.booking.wizard`; month calendar and time buttons (OWL, Odoo colours) |

Not covered: a public booking page for customers (Appointments' public
link). To decide (see the open decisions).

## 3. Field Service → bgg_custom_dev

Field Service was only used for the SSS projects and their tasks.

| Enterprise | Ours |
|---|---|
| `project.project.is_fsm` | `x_is_sss_project` |
| SSS project found by its tasks / name | `x_sss_sale_order_id` (link to its order), set by "Créer tâches SSS" and by migration 19.0.2.1.0 for the existing ones |
| "(CA) Create FSM Project and Tasks" (Studio action) | "Créer tâches SSS" (`action_create_sss_tasks`): plain project flagged SSS, one task per product to install, confirmed and (partly) paid orders only; project manager from the system parameter `bgg.sss_project_manager_login` |

| Field Service task form: client with address and "Voir l'itinéraire", contact number, planned dates, allocated time | Standard task form plus, on SSS tasks only, the client (`partner_id`, with its address), "Voir l'itinéraire" (Google Maps route, `action_bgg_open_itinerary`), the contact number (`partner_phone`, Community), the planned dates (`planned_date_begin` → `date_deadline`) and the allocated time (`allocated_hours`, Community), laid out as in Field Service (left: Assignés, Date prévue, Temps alloué; right: Étiquettes, Client, Numéro de contact); the standard client field and "Date limite" (the end of Date prévue) hidden on SSS tasks; `view_task_form2_inherit_sss` |
| `project.task.planned_date_begin` (Enterprise Planning) | declared in bgg_custom_dev under the same name, so its column and values stay at the uninstall (lost in the rehearsal of 2026-10-30, before this) |

**Stages of the SSS projects.** Each SSS project has "SSS: À faire" and
"SSS: Encours/Fait". Columns added by hand in the Field Service kanban
(2025-12 to 2026-10) created stages linked to every SSS project: 18
"Nouveau" (about 200 tasks in them) and 9 each of Planifié, En cours,
Terminé, Annulé (no task). Some older SSS projects (made in Field Service) had no SSS stage at
all. Migrations 19.0.2.3.0 and 19.0.2.3.1 (post) first give those projects
their two SSS stages, then move the tasks of
"Nouveau" to their project's "SSS: À faire" (confirmed 2026-10-30), takes the other stages off the
SSS projects and deletes them when nothing uses them.

Dropped (not used): worksheets, "under warranty", "allow material".

## 4. Odoo Studio → code

Migration 19.0.2.1.0 moves Studio into the modules, data kept.

**Fields**, declared under the same names (same columns, nothing copied):

| Model | Fields | Module |
|---|---|---|
| sale.order | `x_studio_organisateur_du_rendez_vous`, `x_studio_rendez_vous_pris_la_place_de`, `x_studio_restant_a_facturer`, `x_studio_vendeur_associes` (link table `x_res_users_sale_order_rel`), `x_sale_order_id_project_task_count` | bgg_custom_dev |
| sale.order | `x_studio_payee_commercial`, `x_studio_payee_responsable_commercial`, `x_studio_payee_directeur_commercial` | belgogreen_sales_commission |
| calendar.event | `x_studio_currency_id`, `x_studio_monetary_field_gq_1k2nflo0n`, `x_studio_commercial` (now computed), `x_studio_customer_address`, `x_studio_customer_phone`, `x_studio_rendez_vous_pris_la_place_de` | bgg_custom_dev |

**Views.** The Studio views are switched off and rebuilt as module views:

| Studio view | Module view |
|---|---|
| Calendar list, calendar form | `view_calendar_event_tree_bgg`, `view_calendar_event_form_bgg_layout`, `view_calendar_event_form_bgg_rdv_required` |
| Sale order form | `view_order_form_bgg_studio` |
| Quotations list, sales list | `view_quotation_tree_bgg_studio`, `sale_order_list_upload_bgg_studio` |
| Contact form, contacts list | `view_partner_form_bgg_studio`, `view_partner_tree_bgg_studio` |
| Projects list, all tasks list | `view_project_bgg_studio`, `open_view_all_tasks_list_view_bgg_studio` |
| Payment term form | `view_payment_term_form_bgg_studio` |
| Sellable products list ("Created by", "Created on" columns, category shown; made in Studio on 2026-10-21) | `product_template_list_view_sellable_bgg_studio` (migration 19.0.2.3.0) |
| SMS list, logs list | `sms_sms_view_tree_bgg_studio`, `ir_logging_tree_view_bgg_studio` |
| "Tâches" button action on orders | `action_sale_order_tasks` (tasks of the admin and SSS projects) |
| Appointment buttons and columns, appointment type form (Enterprise screens) | in `bgg_custom_dev_ee`, go with Enterprise |

The 13 Studio views are switched off by migrations 19.0.2.1.0 and
19.0.2.3.0. Left active on purpose, deleted with Studio
(`EE_EXIT_STUDIO_VIEWS_LEFT` in the script): the "all tasks" list and
Field Service's "My tasks" list. Any other active Studio view makes
`ee_preflight` fail.

Lost with Studio on purpose: the timesheet columns of the "all tasks" and
Field Service task lists (Enterprise timesheets).

**Server actions** (all in `bgg_custom_dev/data/sale_order_server_actions.xml`):

| Studio | Ours |
|---|---|
| (CA) Create FSM Project and Tasks | Créer tâches SSS |
| (CA) Rappel pour statuer les rendez-vous énergétique | same name, plus the scheduled job "(JOB) Rappel pour statuer…" (inactive, as in Studio) |
| Clôturer les projets Admin/SSS | same name |
| Recalculate Project deadline | same name |
| (CA) Detect Commercial | `x_studio_commercial` computed by the module |
| – | Recalculer Call Center (Sale Owner) (ours from before, not from Studio) |

The Studio versions are taken out of the Action menu by the migration
(unbound, not deleted) so each action appears once.

**Other.** The Studio group "AMSS ADMIN" (`__custom__.group_58`) is adopted
as `bgg_custom_dev.group_amss_admin` (same group, same members). Saved
filters made in Studio are detached from Studio (kept) and repointed to
our fields.

**Groups** (production, 2026-10-30). All the roles are now declared in the
code. Created by our modules from the start: BGG Dashboard, Direction,
Responsable Dossier, Responsable Dossier Admin (bgg_custom_dev), Commission
User / Manager (belgogreen_sales_commission), PV Simulation User /
Administrator (bgg_pv_simulation), "Prise de RDV (call center)" (bgg_booking,
new), Reconstruction Staging (bgg_staging_rebuild, not taken). Created by
hand or in Studio, **adopted** by bgg_custom_dev (`security/groups.xml`,
noupdate; the migration gives the existing group the xmlid, so members,
menus and rules stay as they are):

| Group | id | Members | Created | xmlid | Adopted by |
|---|---|---|---|---|---|
| Commercial | 59 | 44 | by hand | `bgg_custom_dev.group_commercial` | the module's hook (already on production), declared in 19.0.2.3.0 |
| Call Center | 56 | 6 | by hand | `bgg_custom_dev.group_call_center` | the module's hook (already on production), declared in 19.0.2.3.0 |
| AMSS ADMIN ("Admin" in French) | 58 | 12 | Studio (`__custom__.group_58`) | `bgg_custom_dev.group_amss_admin` | migration 19.0.2.1.0 |
| Administrateur | 57 | 12 | Studio (`__custom__.group_57`) | `bgg_custom_dev.group_administrateur` | migration 19.0.2.3.0 |
| Directeur Commercial | 60 | 2 | by hand | `bgg_custom_dev.group_directeur_commercial` | migration 19.0.2.3.0 |
| Responsable Equipe Commercial | 61 | 2 | by hand | `bgg_custom_dev.group_responsable_equipe_commercial` | migration 19.0.2.3.0 |
| Technicien | 76 | 11 | by hand | `bgg_custom_dev.group_technicien` | migration 19.0.2.3.0 |

On production they give: Call Center 1 menu and 3 record rules, Commercial
1 menu and 1 record rule, each of the other five 1 record rule; no access
rights, no implied groups.

**Who sees which RDV** (record rules on calendar events, made by hand,
adopted in `bgg_custom_dev/security/calendar_rules.xml` by migration
19.0.2.3.0; rules of a user's groups add up):

| Rule (production id) | Groups | Sees | Rights | In the code |
|---|---|---|---|---|
| All Calendar Event for employees (252) | AMSS ADMIN, Administrateur, Commercial, Directeur Commercial, Responsable Equipe Commercial, Technicien | all RDVs | all | same |
| Call Center manage Own Organized Events (251) | Call Center | the RDVs they created | all | same |
| Call Center see Events Only specific appointment type (253) | Call Center | the RDVs of the other types (not the call-centre types) | read only | was `appointment_type_id not in [2, 19]`; now the RDV type codes: not `APT-ENERG-CNT` / `APT-NISOL-CNT`, or no type |
| Call Center manage "public user" Organized Events (428) | Call Center | the RDVs booked online | all | was `create_uid in [4, 46]` (the public users of the two websites); now any public user (`create_uid.share`) |

The migration writes the new conditions of 253 and 428 on the existing
rules.

**Activities** (record rules on `mail.activity`, made by hand, adopted in
`bgg_custom_dev/security/activity_rules.xml` by migration 19.0.2.3.2,
condition kept): "Manage Own Activities or Assigned to Others" (249,
Internal User: activities assigned to or created by the user, or assigned
to a user whose contact's parent has the user's id — `user_id.parent_id`
compares a contact with a user id, as written on production) and
"Administrators can access all activities" (250, Settings: all). Rule 428 is unchanged in practice: on production only the two public users
(4: 6 RDVs, 46: 30 RDVs) are users with `share` who created RDVs.

**Menus made by hand**: "Call Center" (322, group Call Center) and "RDV
Commercial" (324, group Commercial), top-level menus opening the
Enterprise booking pages (URL actions 524 `https://belgogreen.odoo.com/book/callcenter`
and 537 `…/book/commercial`), gone without Appointments. Adopted by
bgg_booking (pre-install hook, migration 19.0.1.4.0 where it is already
installed; `views/menu_views.xml`): same names, groups and place, an app
icon, and they open "Prise de RDV" (each user sees the types they may
book). `ee_preflight` warns about other access rules and menus made by
hand. All 7 groups were still there with
the same members after the uninstall on bsi-staging (2026-10-30).
`ee_preflight` warns about any other group made by hand ("Groups made by
hand, not in a module").

**Automation rules.** Inactive rules 1–19 are old versions of what is now
in bgg_custom_dev; the 5 on appointment answers go with Appointments. The
8 active WhatsApp welcome rules (20–27) wait for WhatsApp on Community
(archived by the uninstall, templates saved in `whatsapp.json`). Rule 16
"Subscribe Admins to FSM Tasks" filters tasks on Field Service's `is_fsm`:
renamed to `project_id.x_is_sss_project` (found in the restore of
2026-10-24).

Checked by `ee_preflight` (Studio section): what is still owned only by
Studio and goes with it.

## 5. Commissions → belgogreen_sales_commission

The module extended the Enterprise plan models; from 19.0.1.0.0 it owns
them:

| Enterprise | Ours |
|---|---|
| `sale.commission.plan` | `bgg.commission.plan` (company, period, state, role percentages, users and hierarchy, paid-invoice requirement) |
| `sale.commission.plan.user` | `bgg.commission.plan.user` |

The migration copies the plans with their ids (every `plan_id` stays
valid), their assignments and chatter; the Enterprise copies are set to
cancelled targets. Also: invoices "in payment" count as paid (system
parameter `belgogreen_sales_commission.count_in_payment_as_paid`), email
template and dashboard fixed for Odoo 19.

Checked by `ee_preflight` (Commissions section) and counted by
`ee_uninstall`: "Commissions (BelGoGreen)", "Commission plans (BelGoGreen)".

## 6. Documents → OCA dms

| Module | Role |
|---|---|
| `dms` | OCA Document Management System 19.0 (OCA/dms 42aec96, unmodified) |
| `bgg_dms` | Folders and files carry their company (`x_company_id`, else the folder's, else the storage's) so the company switcher filters them like Documents; access groups include users internal through a role; file search also matches the folder path; folder shown on cards and in the list |
| `bgg_dms_project` | Project ↔ DMS folder (`x_dms_directory_id`) and "Documents" button, as `documents_project`; new projects get their folder under "Projects" (system parameter `bgg_dms_project.parent_directory`), with the template's sub-folders and the project's company |
| `bgg_documents_dms` | **One-off copy**, removed with Enterprise: same tree (names cleaned and unique), files linked to the same stored files (no copy), archived state, author, dates, tags, chatter, access per top folder, company per folder and file, employee folders under "RH"; can be run again (adds the new ones); table `bgg_documents_dms_map` records what was copied |

Not copied on purpose: spreadsheets, links, shortcuts.

Checked by `ee_preflight` (Documents section) and counted by
`ee_uninstall`: "DMS folders", "DMS files", "DMS file contents",
"Projects with a DMS folder".

## 7. Enterprise look → OCA web_responsive

Full-screen app menu with all apps and search, like the Enterprise home
screen, and a better phone layout. It needs app icons as files: our app
menus (BGG Dashboards, Commissions, Simulation PV, Staging) ship an SVG
icon, and `ee_cleanup` resets the icons Studio set in its own format.

Opening on the apps screen after login, as Enterprise did, is
`web_responsive`'s per-user "Redirect to Home" (Settings → Users →
Preferences; only without a Home Action). Off by default: switched on for
the internal users in the migration guide (Phase 5); new users start
without it.

## 8. The uninstall itself

`tools/ee_exit/ee_uninstall.py` (Odoo shell script) handles what Odoo's
plain uninstall gets wrong for this database:

| Problem with a plain uninstall | What the script does |
|---|---|
| Records Enterprise created but we use (a project with tasks, a stage, an activity type) are deleted, and the links to them emptied | Protected (extra external id) |
| Calendar events linked to an Enterprise model are deleted with the model | Link emptied first, events kept |
| Users get "Internal User" through Enterprise groups that are deleted: they cannot log in | Rights given directly |
| Access rules, filters, menus, automations naming `appointment_type_id`, `appointment_status`, `is_fsm` (projects and tasks) break | Renamed to our fields; `ee_final_check` fails while one is left |
| Uninstalling 129 modules at once runs out of memory and time | Batches, each committed; can resume |
| Locks leave columns and records behind | Retried (`ee_cleanup`) |
| Actions keep gantt/map view types; Studio-format icons break the app menu | Fixed (`ee_cleanup`) |
| Nothing says whether data was lost | Counts of what must survive saved before and compared after (`ee_uninstall`, `ee_final_check`) |
| Nothing says whether everything was moved before | `ee_preflight` |

## 9. OCA modules in the repository

Copied unchanged from OCA (update by copying a newer commit):

| Module | Source | Used for |
|---|---|---|
| `dms` | OCA/dms 19.0, 42aec96 | Documents |
| `resource_booking` | OCA/calendar 19.0, a0f55db | "Prise de RDV" |
| `web_calendar_slot_duration` | OCA/web 19.0, 521be37 | needed by `resource_booking` |
| `web_responsive` | OCA/web 19.0, 521be37 | app menu |

Python package added to `requirements.txt`: `cssselect` (resource_booking).

## 9b. Community server

`deploy/vps/` (README there): Docker instance laid out like the other Odoo
instances of the server (Odoo 19 Community image + the Python libraries of
our modules, its own PostgreSQL 16, nginx, certbot), the restore of an
Odoo.sh dump with the final check, nightly database backups. Not on
Odoo.sh any more: the `vector` PostgreSQL extension of the Enterprise AI
(not needed), the Odoo.sh mail server (own SMTP to configure).

## 10. Not replaced yet

| Feature | Status |
|---|---|
| WhatsApp welcome messages (8 rules) | waiting for OCA `mail_gateway_whatsapp` 19.0 (OCA/mail PR #203) |
| Knowledge (227 articles) | to move to OCA `document_page`, or lost at uninstall |
| Public booking page for customers | to decide |
| Accounting Enterprise (reports, follow-ups, assets, bank sync, CODA) | dropped; bank import and accountant scope still to decide |

## 11. After go-live

Can be removed from the repository once the Community server runs:
`bgg_custom_dev_ee`, `bgg_documents_dms`, `bgg_staging_rebuild`, and the
migrations that read Enterprise tables (they do nothing without them).
Keep `tools/ee_exit/` until the last rehearsal is archived.
