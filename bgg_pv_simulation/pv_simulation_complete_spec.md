# PV Simulation & Quotation Report
## Odoo Custom Module – Functional & Technical Specification
### Version 3.0

---

## 1. Objective

Extend a Sale Order (quotation) with a photovoltaic installation simulation that:

- Auto-detects panels and batteries from sale order line products
- Fetches solar production from **Google Solar API** and **PVGIS**
- Calculates monthly energy balance (charge, vente, achat)
- Calculates monthly financial balance (panel savings, battery savings, sale revenue, purchase cost)
- Generates a branded PDF report with charts and tables
- Lets the salesperson regenerate the simulation on demand, each regeneration bumping a version suffix in the simulation reference

All values in the PDF are reproducible from the stored inputs and the deterministic calculation in `action_compute_daily_balance`.

---

## 2. Scope

### Included
- PV production from PVGIS (with 14 % system losses applied by PVGIS) or from a monthly % profile as fallback
- Consumption modeling (annual total distributed across 12 months with cent-level precision, then split into day / night via a configurable ratio)
- Battery energy flow modeling (charge on surplus, discharge at night)
- Financial calculations (P_buy / P_sell / P_batt from a tariff profile)
- WeasyPrint-based PDF generation (7 pages)
- Chart rendering through matplotlib (3 charts)
- Per-simulation version numbering (`SIM-<SO ref>-vNN`) bumped on every regeneration

### Excluded
- Real-time monitoring
- Shading and weather models
- Multiple installations per simulation

---

## 3. High-Level Architecture

```
res.company
 └── pv_default_cover_photo, pv_default_system_image (Binary)

product.template (inherited)
 ├── panel_unit_power_wc (Float)            ← used when categ path matches "All / Saleable / Panneaux"
 ├── battery_capacity_kwh (Float)           ← used when categ path matches "All / Saleable / Batteries"
 └── battery_efficiency_percent (Float, default 100)

sale.order (inherited)
 ├── pv_simulation_id (Many2one)
 ├── pv_simulation_ids (One2many, multiple simulations allowed per SO)
 └── action_open_pv_simulation button

pv.simulation
 ├── sale_order_id (Many2one, required)
 ├── tariff_profile_id → pv.tariff.profile
 ├── production_profile_id → pv.production.profile (fallback when PVGIS unavailable)
 ├── monthly_result_ids → pv.monthly.result (12 records)
 ├── latitude / longitude (Char, parsed to float with comma/dot tolerance)
 ├── tilt_deg / orientation_deg (Float)
 ├── annual_production_kwh (Google Solar API value)
 ├── pvgis_annual_production_kwh (PVGIS value — primary source)
 ├── battery_capacity_kwh / battery_efficiency (Float, auto-computed from SO)
 ├── default_monthly_consumption_kwh (Float, seeded by wizard from annual input)
 ├── day_consumption_ratio (Float, 0.0 – 1.0, default 0.6)
 ├── purchase_price_kwh / feed_in_tariff_kwh / battery_cost_kwh (per-sim overrides of the tariff profile)
 ├── version (Integer, default 1, readonly, not copied)
 ├── simulation_needs_regeneration (Boolean)
 ├── section_title_* (Char × many, editable per-simulation)
 └── chart_monthly_production / chart_production_vs_consumption / chart_energy_balance (Binary)

pv.monthly.result
 ├── simulation_id (Many2one)
 ├── month (Selection 1–12) + days_in_month (computed: Feb = 29)
 ├── monthly_production_kwh / daily_production_kwh
 ├── monthly_consumption_kwh / monthly_day_consumption_kwh / monthly_night_consumption_kwh
 ├── daily_day_consumption_kwh / daily_night_consumption_kwh
 ├── daily_battery_charge_kwh / daily_energy_sold_kwh / daily_energy_bought_kwh
 ├── monthly_battery_charge_kwh / monthly_energy_sold_kwh / monthly_energy_bought_kwh
 ├── monthly_autoconsumption_kwh / daily_day_autoconsumption_kwh / daily_surplus_pv_kwh
 ├── panel_savings / battery_savings / sale_revenue / purchase_cost / net_balance (Monetary)
 └── battery_charge_level (Integer 0–7, used by icon widget)

pv.production.profile
 └── 12 × *_pct (Float) + total_pct (Computed, validated to 100 ± 0.01 %)

pv.tariff.profile
 └── purchase_price_kwh / feed_in_tariff_kwh / battery_cost_kwh (Monetary)

pv.battery.config
 └── Legacy reference data (no longer the primary source for simulations; retained for admin management)
```

---

## 4. Data flow — Creating a simulation

```
Sale order (with panel + battery products, customer address)
       │
       ▼
  [Wizard — pv.simulation.wizard]
  - Fetches cached GPS from geo.cache or calls Google Geocoding
  - Asks tilt / orientation / annual consumption / day ratio
  - Blocks generation if the SO lacks a panel OR a battery
       │
       ▼
  pv.simulation.create()
  - Name resolved as SIM-<SO ref>-v01
  - tariff_profile_id defaulted to first pv.tariff.profile (if vals didn't supply one)
  - purchase_price_kwh / feed_in_tariff_kwh / battery_cost_kwh seeded from the profile
       │
       ▼
  Client action "pv_simulation_generate" (spinner)
       │
       ▼
  action_do_generate() → calls action_do_regenerate() with skip_version_bump=True
       │
       ├── action_fetch_solar_data(force_update=True)
       │     ├── Google Solar API → building insights, imagery, roof area, max panels
       │     └── _fetch_pvgis_monthly() → monthly kWh + yearly kWh (with loss=14%)
       ├── _compute_monthly_results() — creates 12 monthly_result_ids
       │                                and seeds monthly_consumption_kwh via the
       │                                cent-precise distribution helper
       ├── action_compute_daily_balance() — runs the energy balance formulas
       └── _generate_charts() — builds the 3 chart images
```

After the wizard, every click on **Régénérer la simulation** in the form header runs `action_do_regenerate()` with **no** `skip_version_bump`, so `_bump_version()` fires at the end and renames the simulation to `SIM-<SO>-v02`, `v03`, …

---

## 5. Core formulas

All formulas are implemented in `pv.simulation.action_compute_daily_balance`.

### 5.1 Effective battery capacity

```
cap_bat_effective = battery_capacity_kwh × (battery_efficiency / 100)
```

`battery_capacity_kwh` and `battery_efficiency` are computed from the first battery product found on the sale order (category `All / Saleable / Batteries`).

### 5.2 Daily energy balance (per month)

```
surplus_pv        = max(0, daily_production_kwh − daily_day_consumption_kwh)
autocons_jour     = min(daily_production_kwh, daily_day_consumption_kwh)
charge            = min(surplus_pv, cap_bat_effective)   if cap_bat > 0 else 0
vente             = surplus_pv − charge
energie_bat_nuit  = min(cap_debut_bat + charge, cap_bat_effective) if cap_bat > 0 else 0
achat             = max(0, daily_night_consumption_kwh − energie_bat_nuit)
                  + max(0, daily_day_consumption_kwh  − daily_production_kwh)
```

The achat formula bills **two** shortfalls: the nighttime part the battery can't cover, **and** the daytime part the panels didn't produce.

### 5.3 Battery carryover between months

After each month, the residual state of charge is carried forward:

```
batt_use       = min(energie_bat_nuit, daily_night_consumption_kwh)
cap_debut_bat  = max(0, min(cap_bat_effective, cap_debut_bat + charge − batt_use))
```

The next month's computation starts with this `cap_debut_bat`.

### 5.4 Monthly aggregation

```
monthly_battery_charge_kwh  = charge × days_in_month
monthly_energy_sold_kwh     = vente × days_in_month
monthly_energy_bought_kwh   = achat × days_in_month
monthly_autoconsumption_kwh = (autocons_jour + batt_use) × days_in_month
```

### 5.5 Financial (per month)

```
eco_panneaux  = autocons_jour × days × P_buy
revenu_vente  = vente × days × P_sell
eco_batterie  = batt_use × days × (P_buy − P_batt)
cout_achat    = achat × days × P_buy
net_balance   = cout_achat − revenu_vente
```

All values are rounded to 2 decimals at the store boundary.

### 5.6 Annual totals (Bilan Énergétique page)

`_compute_bilan` sums each monthly field (`sum(results.mapped(...))`). The annual production total is taken verbatim from `pvgis_annual_production_kwh` (primary source) or `annual_production_kwh` (fallback); it is **not** re-summed from the monthly values, to avoid floating-point drift.

### 5.7 Cent-precise annual consumption distribution

When the wizard stores `default_monthly_consumption_kwh = annual / 12`, naively writing `round(monthly, 2)` for each of the 12 months causes drift (5000 → 5000.04). The helper `_distribute_annual_consumption(annual, count=12)` spreads the total in cents so that:

- every per-month value has at most 2 decimals,
- the sum equals the original annual input exactly.

Example — annual = 5000: eight months of 416.67 + four months of 416.66 = 5000.00.

---

## 6. Simulation reference format

```
SIM-<sale order reference>-v<NN>
```

- `NN` is the generation version, zero-padded on 2 digits (`v01`, `v02`, …)
- New simulations always start at `v01`
- Each click on **Régénérer la simulation** runs `_bump_version()` at the end of `action_do_regenerate()`, which `+1`'s the `version` field and rewrites the `name`
- The initial wizard generation passes `skip_version_bump=True` via context, so a freshly-created simulation stays on `v01` after its first run
- `version` is `copy=False`, so duplicating a simulation resets it to 1

Fallback: if `_next_simulation_reference()` is called without a sale order (legacy or direct Python calls), it falls back to the `ir.sequence` with code `pv.simulation` which yields `SIM-00001`, `SIM-00002`, …

---

## 7. Report — WeasyPrint PDF

The primary report generator is `pv.simulation.weasyprint.generator` (`models/report_generator_weasyprint.py`). The QWeb template in `report/pv_simulation_template.xml` exists as a fallback/alternative but is not wired to the UI button.

### 7.1 Page order

| Page | Section | Editable title fields on pv.simulation |
|------|---------|----------------------------------------|
| 1 | Couverture | `cover_title`, `cover_subtitle` (+ photo) |
| 2 | BILAN ÉNERGÉTIQUE | `section_title_bilan` |
| 3 | BILAN ANNUEL (charts) | `section_title_bilan_annuel`, `section_title_bilan_annuel_prod_vs_conso`, `section_title_bilan_annuel_repartition` |
| 4 | Localisation | `section_title_location` |
| 5 | Production + système | `section_title_production`, `section_title_system` |
| 6 | Données de consommation | `section_title_consumption`, `section_title_monthly_data`, `section_title_daily_balance` |
| 7 | Bilan financier mensuel | `section_title_financial` |

Every section title can also be overridden per simulation from the matching tab in the form view.

### 7.2 Styling highlights

- Production colour: `#8BC34A` (bar chart, donut outer ring, Total économies value)
- Autoconso / Conso nuit: `#1F6C6C`
- Vente: `#F39C12`
- Achat: `#F8C9CA`
- Inner consommation disk: `#111111`
- "Total économies" card: white background, black label, value in `#8BC34A` with a piggy-bank SVG in the same green
- Donut value labels are formatted as `{value:,.2f} kWh`

---

## 8. Form view (Odoo UI)

The simulation form exposes one tab per report page so the salesperson can edit everything inline:

1. **Système PV** — auto-computed (panel count, power, battery capacity, efficiency, orientation, tilt)
2. **Couverture (Page 1)**
3. **Bilan Énergétique (Page 2)** — read-only summary (production, consommation, autoconso, économies)
4. **Bilan Annuel (Page 3)** — editable titles + previews of the two charts
5. **Localisation (Page 4)**
6. **Production (Page 5)**
7. **Consommation (Page 6)** — editable monthly consumption table with day/night ratio helpers
8. **Bilan Financier (Page 7)** — tariff profile selection + editable price overrides + editable monthly financial table

Editable fields are highlighted in **light blue** (`#E3F2FD` / `#90CAF9`) via the `o_field_highlight` CSS class and the `pv_editable_table` list class, so the salesperson sees what is computed vs. what they can change.

A warning banner at the top of the form appears whenever `simulation_needs_regeneration = True` (triggered by writes to any field in `SIMULATION_IMPACTING_FIELDS`).

---

## 9. External APIs

### 9.1 Google Solar API

- Called from `action_fetch_solar_data`
- Provides: building insights, annual energy, roof area, max panels, imagery
- Configured via `ir.config_parameter` `google_api_key`
- Requires latitude/longitude and `total_pv_power_wc > 0`
- Scaled to the actual panel count and wattage on the sale order

### 9.2 PVGIS (EU Science Hub)

- Endpoint: `https://re.jrc.ec.europa.eu/api/v5_3/PVcalc`
- Parameters passed: `lat`, `lon`, `peakpower` (kW), `loss=14`, `pvtechchoice=crystSi`, `mountingplace=building`, optional `angle` and `aspect`
- The **14 % system loss is sent to PVGIS and applied server-side**; no further loss is subtracted locally
- Response provides 12 monthly `E_m` values and a yearly `E_y` total, both already net of losses

### 9.3 Google Geocoding (optional)

- Used by the wizard to resolve the customer address into latitude/longitude
- Cached in `geo.cache` per partner to avoid redundant API calls

---

## 10. Security

| Group | Model | Rights |
|-------|-------|--------|
| `group_pv_user` (implies `sales_team.group_sale_salesman`) | `pv.simulation`, `pv.monthly.result` | Read/write/create/unlink, restricted to simulations on sale orders owned by the user |
| `group_pv_admin` (implies `group_pv_user`) | Same models | Full access |

Record rules enforce the "own sale orders only" scope for the user group.

---

## 11. Demo data

- `pv_production_profile_data.xml` — "Profil Standard Belgique" (monthly % for Belgium)
- `pv_tariff_profile_data.xml` — Default tariff (P_buy, P_sell, P_batt)
- `pv_battery_config_data.xml` — Legacy battery configurations
- `demo/pv_simulation_demo.xml` — Sample sale orders and simulations

---

## 12. Tests

The `tests/` package covers the core deterministic logic without hitting any external API. Every test class inherits `PvSimulationTestBase` (`tests/common.py`) which sets up a sale order with a panel product and a battery product in the expected categories, plus a tariff profile.

| Test file | What it covers |
|-----------|----------------|
| `test_consumption_distribution.py` | Cent-precise annual split: 5000 → 5000, no drift; custom totals, custom counts, safe edge cases |
| `test_energy_balance.py` | `action_compute_daily_balance` formulas: surplus/charge/vente/achat, day shortfall billing, no-battery case, monthly × days aggregation, financial outputs |
| `test_simulation_reference.py` | `_format_simulation_name` padding, new simulations start at v01, `_bump_version` behaviour, `copy` resets version, legacy sequence fallback |
| `test_production_profile.py` | Profile sum-to-100 validation, `get_month_pct` lookup, out-of-range months |
| `test_product_category.py` | `_is_panel_category` / `_is_battery_category` helpers, panel/battery auto-detection from SO lines, default battery efficiency = 100 % |
| `test_simulation_create.py` | `create()` auto-applies the first tariff profile, honours explicit overrides, formats the SIM reference, multiple simulations for the same SO both start at v01 |

Run with:
```bash
odoo --test-enable -i bgg_pv_simulation --test-tags=bgg_pv_simulation
```

---

## 13. File layout

```
bgg_pv_simulation/
├── __manifest__.py
├── __init__.py
├── data/
│   ├── solar_api_config.xml
│   ├── pv_battery_config_data.xml
│   ├── pv_production_profile_data.xml
│   └── pv_tariff_profile_data.xml
├── demo/
│   └── pv_simulation_demo.xml
├── docs/
│   └── glossaire_variables_pv.html
├── models/
│   ├── geo_cache.py
│   ├── product_template.py
│   ├── pv_battery_config.py
│   ├── pv_monthly_result.py
│   ├── pv_production_profile.py
│   ├── pv_report_defaults.py
│   ├── pv_simulation.py
│   ├── pv_tariff_profile.py
│   ├── report_generator_weasyprint.py
│   ├── res_company.py
│   ├── sale_order.py
│   └── solar_api_client.py
├── report/
│   ├── pv_simulation_report.xml
│   └── pv_simulation_template.xml
├── security/
│   ├── ir.model.access.csv
│   └── pv_simulation_security.xml
├── static/src/
│   ├── css/pv_simulation.css
│   ├── js/battery_icon_widget.js
│   ├── js/pv_simulation_regenerate.js
│   └── xml/pv_simulation_templates.xml
├── tests/
│   ├── __init__.py
│   ├── common.py
│   ├── test_consumption_distribution.py
│   ├── test_energy_balance.py
│   ├── test_product_category.py
│   ├── test_production_profile.py
│   ├── test_simulation_create.py
│   └── test_simulation_reference.py
├── views/
│   ├── menu_views.xml
│   ├── product_template_views.xml
│   ├── pv_battery_config_views.xml
│   ├── pv_monthly_result_views.xml
│   ├── pv_production_profile_views.xml
│   ├── pv_simulation_views.xml
│   ├── pv_tariff_profile_views.xml
│   ├── res_company_views.xml
│   └── sale_order_views.xml
└── wizard/
    ├── pv_simulation_wizard.py
    └── pv_simulation_wizard_views.xml
```

---

## 14. Technical constraints

- **Odoo version:** 17.0+ (tested on 17)
- **Python:** 3.10+ (report generator uses nested f-strings, requires 3.12+ to compile standalone)
- **External deps:** `matplotlib`, `requests`, `weasyprint`
- **Determinism:** Every formula in `action_compute_daily_balance` runs on stored inputs only; reproducing the values in the PDF never requires re-contacting an external API (the API results are persisted into `pv.monthly.result` and `pvgis_annual_production_kwh`).

---

*End of Specification v3.0*
