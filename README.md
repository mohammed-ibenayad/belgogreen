# BelGoGreen Odoo Addons

Custom Odoo 19 addons developed for **BelGoGreen** — a Belgian photovoltaic installer. The repository contains four independent modules, each with its own manifest, views and docs.

## Modules

| Module | Purpose |
|---|---|
| [`bgg_custom_dev`](bgg_custom_dev/) | Extends core Odoo models (appointments, calendar, projects, sales orders) with BelGoGreen-specific business logic: spouse contact sync, organizer auto-assignment, NoShow activities, clickable phones/addresses, welcome-call deadlines, phone-based customer deduplication, "Dossier" tab on sales orders with a "Responsable" (project manager of the order, picked from the "Responsable Dossier" group). |
| [`bgg_pv_simulation`](bgg_pv_simulation/) | Generates a full photovoltaic simulation from a sale order: Google Solar API + PVGIS production, monthly energy balance (charge / vente / achat), monthly financial balance, and a branded 7-page WeasyPrint PDF report. See [`pv_simulation_complete_spec.md`](bgg_pv_simulation/pv_simulation_complete_spec.md). |
| [`belgogreen_sales_commission`](belgogreen_sales_commission/) | Hierarchical commission engine: multi-level calculation (salesperson → team leader → director), auto-creation on invoice payment, claim/approval workflow, role-based percentages, team dashboards. |
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
