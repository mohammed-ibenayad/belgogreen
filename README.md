# BelGoGreen Odoo Addons

Custom Odoo 19 addons developed for **BelGoGreen** — a Belgian photovoltaic installer. The repository contains five modules, each with its own manifest, views and docs.

## Modules

| Module | Purpose |
|---|---|
| [`bgg_custom_dev`](bgg_custom_dev/) | Extends core Odoo models (appointments, calendar, projects, sales orders) with BelGoGreen-specific business logic: spouse contact sync, organizer auto-assignment, NoShow activities, clickable phones/addresses, phone-based customer deduplication, "Dossier" tab on sales orders with a "Responsable" (project manager of the order, picked from the "Responsable Dossier" group, set only by the "Responsable Dossier Admin" group, propagated to the order's projects and tasks), admin project deadlines computed from the payment term and product categories (rules in the `bgg.admin_project_deadline_rules` system parameter; project end = field service reference end + 10 business days), with the project manager and planned dates locked against manual edits on those projects; "Bloqué" status for admin projects and their tasks (Responsable Dossier group; a blocked task blocks its project); "AMSS Management" dashboard for the Direction group (CA NET, Ventes Confirmées, TX Conversion, Chantiers en retard, Dossiers bloqués, CA signé / facturé / encaissé, Carnet de commandes); admin projects become Terminé once all their tasks are closed. Also holds the former Odoo Studio customizations (fields, views, saved filters, "AMSS ADMIN" group) and actions: "Créer tâches SSS" (SSS project linked to the order + one task per product to install, for confirmed and paid orders), "Clôturer les projets Admin/SSS", "Rappel pour statuer les rendez-vous énergétique" (Action menu + inactive daily job), "Recalculate Project deadline". |
| [`bgg_custom_dev_ee`](bgg_custom_dev_ee/) | Enterprise bridge for `bgg_custom_dev`, installed automatically while Odoo Enterprise is there and removed with it when moving to Community. `bgg_custom_dev` itself no longer depends on Enterprise: its rules use its own RDV type (`bgg.rdv.type`), RDV status and questionnaire summary on calendar events, and SSS project flag. The bridge keeps them in sync with Appointments (type and status both ways) and Field Service (`is_fsm`), and holds the Enterprise-only automations (appointment questionnaire: spouse contact, address, title, "pris à la place de"; documents folder name), the Field Service values of the SSS projects / tasks and the Studio view changes on Enterprise screens. |
| [`bgg_pv_simulation`](bgg_pv_simulation/) | Generates a full photovoltaic simulation from a sale order: Google Solar API + PVGIS production, monthly energy balance (charge / vente / achat), monthly financial balance, and a branded 7-page WeasyPrint PDF report. See [`pv_simulation_complete_spec.md`](bgg_pv_simulation/pv_simulation_complete_spec.md). |
| [`belgogreen_sales_commission`](belgogreen_sales_commission/) | Hierarchical commission engine: multi-level calculation (salesperson → team leader → director), auto-creation on invoice payment, claim/approval workflow, role-based percentages, team dashboards. Owns its commission plans (`bgg.commission.plan`), so it no longer needs the Enterprise `sale_commission` module; invoices "In payment" count as paid (system parameter `belgogreen_sales_commission.count_in_payment_as_paid`). |
| [`bgg_staging_rebuild`](bgg_staging_rebuild/) | Lets a privileged business user rebuild the Odoo.sh staging environment from inside Odoo, without GitHub or Odoo.sh dashboard access. Wizard triggers a fast-forward of staging onto production (or an empty commit) via the GitHub API; build progress is read from GitHub commit statuses and every trigger is logged for audit. Configuration lives in `ir.config_parameter` (owner, repo, token, branches, strategy, cooldown). |

## End-user guides (French)

- [`docs/Guide_Utilisateur_Commissions.md`](docs/Guide_Utilisateur_Commissions.md) — salesperson guide for the commission module
- [`docs/Guide_Manager_Commissions.md`](docs/Guide_Manager_Commissions.md) — manager guide for approvals and payouts
- [`docs/Guide_Utilisateur_Simulation_PV.md`](docs/Guide_Utilisateur_Simulation_PV.md) — salesperson guide for the PV simulation module

## Installation

1. Copy the module directory (or the whole repo) into your Odoo addons path
2. Install Python dependencies: `pip install -r requirements.txt`
3. From Odoo, **Apps → Update Apps List**, then search and install the modules you need

## Running the tests

```bash
# Custom development (appointment / calendar / project extensions)
odoo --test-enable -i bgg_custom_dev --test-tags=bgg_custom_dev

# PV simulation core logic
odoo --test-enable -i bgg_pv_simulation --test-tags=bgg_pv_simulation

# Sales commission
odoo --test-enable -i belgogreen_sales_commission --test-tags=belgogreen_sales_commission
```

## Technical

- **Odoo version:** 19.0
- **License:** LGPL-3
- **Author:** BelGoGreen — <https://www.belgogreen.com>
