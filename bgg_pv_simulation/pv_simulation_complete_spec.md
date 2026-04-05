# PV Simulation & Quotation Report
## Odoo Custom Module – Complete Functional & Technical Specification
### Version 2.0

---

## 1. Objective

Develop a **custom Odoo module** that extends the standard **Quotation (sale.order)** to:

- Simulate a **photovoltaic (PV) installation**
- Compute **energy production, consumption, storage, grid sale, and grid purchase**
- Compute **monthly and annual financial impacts**
- Generate a **PDF simulation report** matching the provided Excel & PDF logic

All values in the PDF **must be reproducible from stored inputs and deterministic calculations**.

---

## 2. Scope

### Included
- PV production simulation (annual → monthly via % profile)
- Consumption modeling (day / night)
- Battery energy flow modeling
- Financial ROI simulation
- QWeb PDF generation from quotation
- Chart/graph generation for PDF reports
- Company branding configuration
- Location image support

### Excluded
- Real-time monitoring
- External PV yield APIs
- Shading / weather physics models
- Automatic satellite image retrieval

---

## 3. High-Level Architecture

```
res.company
 └── PV Report branding fields

sale.order
 └── pv.simulation (1:1)
      ├── pv.consumption.profile (Many2one)
      ├── pv.production.profile (Many2one)
      ├── pv.battery.config (Many2one)
      ├── pv.tariff.profile (Many2one)
      ├── pv.monthly.result (One2many, 12 records)
      └── Chart images (Binary, computed)
```

---

## 4. Data Models

---

### 4.1 res.company (Extended)

**Purpose:**  
Store company branding and contact information for PDF headers/footers.

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| pv_report_logo | Binary | Logo image for PV reports (recommended: 200x80px PNG) |
| pv_report_phone | Char | Contact phone for reports |
| pv_report_email | Char | Contact email for reports |
| pv_report_tagline | Char | Company tagline (e.g., "Save your planet. Save your wallet.") |

**Notes:**
- Falls back to standard `res.company` fields if PV-specific fields are empty
- Logo should support transparent backgrounds

---

### 4.2 pv.simulation

**Purpose:**  
Central object containing all simulation inputs and computed results.

**Table:** `pv_simulation`

**Relations:**
- `sale_order_id` → sale.order (Many2one, required)
- `monthly_result_ids` → pv.monthly.result (One2many)

---

#### 4.2.1 Core Fields

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Simulation reference (auto-generated) |
| sale_order_id | Many2one | Related quotation |
| currency_id | Many2one | Currency (default: company currency) |
| installation_address | Char | Installation location (required) |
| latitude | Float | Optional, for future map integration |
| longitude | Float | Optional, for future map integration |
| location_image | Binary | Uploaded satellite/map image |
| location_image_filename | Char | Original filename |
| report_date | Date | Date shown on report (default: today) |
| validity_days | Integer | Quotation validity period |
| notes | Text | Additional notes for report |

---

#### 4.2.2 PV System Parameters

| Field | Type | Description |
|-------|------|-------------|
| roof_surface_m2 | Float | Roof surface in m² |
| total_pv_power_wc | Float | Installed PV power in Wc (required) |
| orientation_deg | Float | Panel orientation in degrees (-180 to 180, 0=South) |
| tilt_deg | Float | Panel inclination in degrees (0-90) |

---

#### 4.2.3 Production Configuration

| Field | Type | Description |
|-------|------|-------------|
| annual_production_kwh | Float | Total yearly PV production (required) |
| production_profile_id | Many2one | Monthly % distribution profile (required) |

---

#### 4.2.4 Linked Profiles

| Field | Type | Description |
|-------|------|-------------|
| consumption_profile_id | Many2one | Consumption model (required) |
| battery_config_id | Many2one | Battery technical data (required) |
| tariff_profile_id | Many2one | Electricity prices (required) |

---

#### 4.2.5 Annual Computed Fields (Energy)

| Field | Type | Description |
|-------|------|-------------|
| annual_production_calc_kwh | Float | Computed sum of monthly production |
| annual_consumption_kwh | Float | Total annual consumption |
| annual_day_consumption_kwh | Float | Annual day consumption |
| annual_night_consumption_kwh | Float | Annual night consumption |
| annual_day_autoconsumption_kwh | Float | Direct daytime self-consumption |
| annual_autoconsumption_kwh | Float | Total (direct + battery) |
| annual_battery_charge_kwh | Float | Total energy stored in battery |
| annual_energy_sold_kwh | Float | Total energy sold to grid |
| annual_energy_bought_kwh | Float | Total energy purchased from grid |

---

#### 4.2.6 Annual Computed Fields (Financial)

| Field | Type | Description |
|-------|------|-------------|
| total_panel_savings | Monetary | € saved from direct consumption |
| total_battery_savings | Monetary | € saved from battery usage |
| total_sale_revenue | Monetary | € earned from grid sales |
| total_purchase_cost | Monetary | € spent on grid purchases |
| total_savings | Monetary | Net savings (panel + battery + sale - purchase) |

---

#### 4.2.7 Chart Images (Computed Binary Fields)

| Field | Type | Description |
|-------|------|-------------|
| chart_monthly_production | Binary | PNG: Monthly daily production bar chart |
| chart_production_consumption | Binary | PNG: Production vs consumption stacked bar |
| chart_annual_bar | Binary | PNG: Annual balance bar chart |
| chart_annual_donut | Binary | PNG: Annual summary donut chart |

---

### 4.3 pv.consumption.profile

**Purpose:**  
Defines electricity usage behavior.

**Table:** `pv_consumption_profile`

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Profile name |
| annual_consumption_kwh | Float | Total yearly consumption |
| monthly_consumption_kwh | Float | Computed: annual / 12 |
| daily_day_consumption_kwh | Float | Daily daytime usage (required) |
| daily_night_consumption_kwh | Float | Daily nighttime usage (required) |
| daily_total_consumption_kwh | Float | Computed: day + night |

**Computed Fields:**
```python
monthly_consumption_kwh = annual_consumption_kwh / 12
daily_total_consumption_kwh = daily_day_consumption_kwh + daily_night_consumption_kwh
```

---

### 4.4 pv.production.profile

**Purpose:**  
Defines **monthly percentage distribution** of annual production.

**Table:** `pv_production_profile`

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Profile name |
| january_pct | Float | % of annual production |
| february_pct | Float | % |
| march_pct | Float | % |
| april_pct | Float | % |
| may_pct | Float | % |
| june_pct | Float | % |
| july_pct | Float | % |
| august_pct | Float | % |
| september_pct | Float | % |
| october_pct | Float | % |
| november_pct | Float | % |
| december_pct | Float | % |
| total_pct | Float | Computed, must = 100% |

**Validation:**
```python
@api.constrains('january_pct', 'february_pct', ..., 'december_pct')
def _check_total_percentage(self):
    for record in self:
        total = sum([
            record.january_pct, record.february_pct, record.march_pct,
            record.april_pct, record.may_pct, record.june_pct,
            record.july_pct, record.august_pct, record.september_pct,
            record.october_pct, record.november_pct, record.december_pct
        ])
        if abs(total - 100.0) > 0.01:
            raise ValidationError(
                _('Monthly percentages must sum to 100%%. Current: %.2f%%') % total
            )
```

---

### 4.5 pv.battery.config

**Purpose:**  
Defines battery behavior and costs.

**Table:** `pv_battery_config`

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Configuration name |
| capacity_kwh | Float | Nominal capacity in kWh |
| usable_ratio | Float | Usable % (0–1), typically 0.90–0.95 |
| max_daily_charge_kwh | Float | Maximum daily charge limit |
| efficiency | Float | Round-trip efficiency (0–1) |
| cost_per_kwh | Monetary | Degradation cost per kWh cycled |

**Validation:**
```python
@api.constrains('usable_ratio', 'efficiency')
def _check_ratios(self):
    for record in self:
        if not (0 < record.usable_ratio <= 1):
            raise ValidationError(_('Usable ratio must be between 0 and 1'))
        if not (0 < record.efficiency <= 1):
            raise ValidationError(_('Efficiency must be between 0 and 1'))
```

**Note:** `max_daily_charge_kwh` is an independent parameter that may exceed `capacity_kwh × usable_ratio` due to charge rate configurations by the installer.

---

### 4.6 pv.tariff.profile

**Purpose:**  
Defines energy prices for financial calculations.

**Table:** `pv_tariff_profile`

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Tariff name |
| purchase_price_kwh | Monetary | Grid purchase price (€/kWh) |
| feed_in_tariff_kwh | Monetary | Grid sale price (€/kWh) |
| currency_id | Many2one | Currency reference |

---

### 4.7 pv.monthly.result

**Purpose:**  
Stores computed monthly simulation results (12 records per simulation).

**Table:** `pv_monthly_result`

| Field | Type | Description |
|-------|------|-------------|
| simulation_id | Many2one | Parent simulation |
| month | Selection | 1-12 (Jan–Dec) |
| month_name | Char | Computed: French month name |
| days_in_month | Integer | Calendar-based (28-31) |

**Energy Fields (Monthly Totals):**

| Field | Type | Description |
|-------|------|-------------|
| monthly_production_kwh | Float | Total production for month |
| monthly_consumption_kwh | Float | Total consumption for month |
| monthly_day_consumption_kwh | Float | Day consumption for month |
| monthly_night_consumption_kwh | Float | Night consumption for month |
| monthly_battery_charge_kwh | Float | Energy stored for month |
| monthly_energy_sold_kwh | Float | Energy sold for month |
| monthly_energy_bought_kwh | Float | Energy bought for month |
| monthly_autoconsumption_kwh | Float | Total self-consumed for month |

**Energy Fields (Daily Averages):**

| Field | Type | Description |
|-------|------|-------------|
| daily_production_kwh | Float | Average daily production |
| daily_day_consumption_kwh | Float | Daily day consumption |
| daily_night_consumption_kwh | Float | Daily night consumption |
| daily_day_autoconsumption_kwh | Float | Daily direct self-consumption |
| daily_battery_charge_kwh | Float | Daily battery charge |
| daily_energy_sold_kwh | Float | Daily energy sold |
| daily_energy_bought_kwh | Float | Daily energy bought |

**Financial Fields (Monthly Totals):**

| Field | Type | Description |
|-------|------|-------------|
| panel_savings | Monetary | € saved from panels |
| battery_savings | Monetary | € saved from battery |
| sale_revenue | Monetary | € from grid sales |
| purchase_cost | Monetary | € for grid purchases |
| net_balance | Monetary | purchase_cost - sale_revenue |

---

## 5. Calculation Logic

---

### 5.1 Days in Month

Use calendar-based values (non-leap year default):

| Month | Days |
|-------|------|
| January | 31 |
| February | 28 |
| March | 31 |
| April | 30 |
| May | 31 |
| June | 30 |
| July | 31 |
| August | 31 |
| September | 30 |
| October | 31 |
| November | 30 |
| December | 31 |

**Implementation:** Use `calendar.monthrange()` or hardcoded values.

---

### 5.2 Monthly Production

```python
monthly_production_kwh = annual_production_kwh × (monthly_pct / 100)
```

---

### 5.3 Daily Production

```python
daily_production_kwh = monthly_production_kwh / days_in_month
```

---

### 5.4 Daily Energy Balance

```python
# Step 1: Direct self-consumption (daytime)
daily_day_autoconsumption = min(daily_production_kwh, daily_day_consumption_kwh)

# Step 2: Surplus available for battery
surplus = daily_production_kwh - daily_day_autoconsumption

# Step 3: Battery charge (with limits)
effective_usable_capacity = battery.capacity_kwh × battery.usable_ratio
max_charge = min(battery.max_daily_charge_kwh, effective_usable_capacity)
daily_battery_charge = min(surplus, max_charge) if surplus > 0 else 0

# Step 4: Energy sold to grid (remaining surplus)
daily_energy_sold = max(surplus - daily_battery_charge, 0)

# Step 5: Energy bought from grid
unmet_day_consumption = daily_day_consumption_kwh - daily_day_autoconsumption
unmet_night_consumption = daily_night_consumption_kwh - daily_battery_charge
daily_energy_bought = max(unmet_day_consumption + unmet_night_consumption, 0)
```

---

### 5.5 Monthly Aggregation

```python
monthly_battery_charge_kwh = daily_battery_charge × days_in_month
monthly_energy_sold_kwh = daily_energy_sold × days_in_month
monthly_energy_bought_kwh = daily_energy_bought × days_in_month
monthly_autoconsumption_kwh = (daily_day_autoconsumption + daily_battery_charge) × days_in_month
```

---

### 5.6 Daily Financial Calculations

```python
# Panel savings: money saved by using solar instead of buying from grid
daily_panel_savings = daily_day_autoconsumption × purchase_price_kwh

# Battery savings: money saved by using stored energy at night
# Accounts for battery degradation cost
daily_battery_savings = daily_battery_charge × (purchase_price_kwh - battery.cost_per_kwh)

# Sale revenue: money earned from selling excess to grid
daily_sale_revenue = daily_energy_sold × feed_in_tariff_kwh

# Purchase cost: money spent buying from grid
daily_purchase_cost = daily_energy_bought × purchase_price_kwh
```

---

### 5.7 Monthly Financial Aggregation

```python
panel_savings = daily_panel_savings × days_in_month
battery_savings = daily_battery_savings × days_in_month
sale_revenue = daily_sale_revenue × days_in_month
purchase_cost = daily_purchase_cost × days_in_month
net_balance = purchase_cost - sale_revenue  # Positive = cost, Negative = profit
```

---

### 5.8 Annual Totals

```python
annual_production_calc_kwh = sum(m.monthly_production_kwh for m in monthly_results)
annual_consumption_kwh = sum(m.monthly_consumption_kwh for m in monthly_results)
annual_day_consumption_kwh = sum(m.monthly_day_consumption_kwh for m in monthly_results)
annual_night_consumption_kwh = sum(m.monthly_night_consumption_kwh for m in monthly_results)
annual_day_autoconsumption_kwh = sum(m.daily_day_autoconsumption_kwh * m.days_in_month for m in monthly_results)
annual_battery_charge_kwh = sum(m.monthly_battery_charge_kwh for m in monthly_results)
annual_autoconsumption_kwh = annual_day_autoconsumption_kwh + annual_battery_charge_kwh
annual_energy_sold_kwh = sum(m.monthly_energy_sold_kwh for m in monthly_results)
annual_energy_bought_kwh = sum(m.monthly_energy_bought_kwh for m in monthly_results)

total_panel_savings = sum(m.panel_savings for m in monthly_results)
total_battery_savings = sum(m.battery_savings for m in monthly_results)
total_sale_revenue = sum(m.sale_revenue for m in monthly_results)
total_purchase_cost = sum(m.purchase_cost for m in monthly_results)
total_savings = total_panel_savings + total_battery_savings + total_sale_revenue
```

---

## 6. Integration with Sale Order

### 6.1 Relationship
- One quotation → one PV simulation (1:1)
- Simulation linked via `sale_order_id`

### 6.2 User Interface
- Button on quotation form: **"PV Simulation"**
- Opens simulation form view
- Button to regenerate PDF report

### 6.3 Recalculation Triggers
- Product quantity changes (panel count affects `total_pv_power_wc`)
- Profile changes (consumption, production, battery, tariff)
- Manual trigger via button

### 6.4 Material Pricing
- Standard Odoo `sale.order.line` logic
- Products displayed in PDF from quotation lines

---

## 7. PDF Report Specification

### 7.1 Report Type
- QWeb PDF template
- wkhtmltopdf rendering
- Pre-rendered chart images (PNG)

### 7.2 Page Layout

| Element | Specification |
|---------|---------------|
| Page Size | A4 (595.28 × 841.89 points) |
| Margins | Top: 20mm, Bottom: 25mm, Left: 15mm, Right: 15mm |
| Header Height | 15mm (logo + contact info) |
| Footer Height | 20mm (address, email, phone, VAT) |

### 7.3 Header (All Pages Except Cover)

| Element | Source |
|---------|--------|
| Company Logo | `res.company.pv_report_logo` or `res.company.logo` |
| Company Name | `res.company.name` |

### 7.4 Footer (All Pages)

| Element | Source |
|---------|--------|
| Address | `res.company.street`, `res.company.zip`, `res.company.city` |
| Email | `res.company.pv_report_email` or `res.company.email` |
| Phone | `res.company.pv_report_phone` or `res.company.phone` |
| VAT | `res.company.vat` |

---

### 7.5 Page 1: Cover Page

| Element | Source | Notes |
|---------|--------|-------|
| Company Logo | `res.company.pv_report_logo` | Top-right corner |
| Hero Image | Static asset | Worker installing panels |
| Title | "VOTRE INSTALLATION PHOTOVOLTAÏQUE" | Primary heading, green (#8BC34A) |
| Tagline | `res.company.pv_report_tagline` or default | Italicized subtitle |
| Footer | Company contact details | Full width |

---

### 7.6 Page 2: Installation Location & Production

**Section 1: Location**

| Element | Source | Format |
|---------|--------|--------|
| Section Title | "LOCALISATION DE L'INSTALLATION" | Heading |
| Address | `pv.simulation.installation_address` | Text |
| Roof Surface | `pv.simulation.roof_surface_m2` | "X m²" |
| Location Image | `pv.simulation.location_image` | 400×250px max |

**Section 2: Average Daily Production**

| Element | Source | Format |
|---------|--------|--------|
| Section Title | "PRODUCTION MOYENNE JOURNALIÈRE" | Heading |
| Panel Power | `pv.simulation.total_pv_power_wc` | "XXXXXWc" |
| Orientation | `pv.simulation.orientation_deg` | "X°" |
| Inclination | `pv.simulation.tilt_deg` | "X°" |
| Bar Chart | `pv.simulation.chart_monthly_production` | Monthly daily production |
| Annual Total | `pv.simulation.annual_production_kwh` | "XXXXX.XX kWh" |

---

### 7.7 Page 3: Consumption Data & Energy Balance

**Section 1: Monthly/Daily Data Table**

| Column | Source | Format |
|--------|--------|--------|
| Mois | `pv.monthly.result.month_name` | French name |
| Production (Monthly) | `monthly_production_kwh` | "X.XX kWh" |
| Consumption (Monthly) | `monthly_consumption_kwh` | "X.XX kWh" |
| Production (Daily) | `daily_production_kwh` | "X.XX kWh" |
| Conso de nuit | `daily_night_consumption_kwh` | "X.XX kWh" |
| Conso de jour | `daily_day_consumption_kwh` | "X.XX kWh" |

**Section 2: Explanation Box**

```
La charge est l'énergie disponible dans la batterie. Elle dépend de la capacité 
de la batterie et du surplus de production par rapport à la consommation de jour. 
Elle tient également compte du pourcentage de batterie utilisable et de sa performance.

La vente est l'énergie produite qui ne peut pas être auto-consommée (ni en 
consommation de jour, ni pour charger la batterie). Elle sera alors revendue sur le réseau.

L'achat correspond à l'énergie qu'il faut acheter sur le réseau, en déduisant 
la partie auto-consommation.
```

**Section 3: Daily Energy Balance Table**

| Column | Source | Format |
|--------|--------|--------|
| Mois | Month name | French |
| Production | `daily_production_kwh` | "X.XX" |
| Conso jour | `daily_day_consumption_kwh` | "X.XX" |
| Conso nuit | `daily_night_consumption_kwh` | "X.XX" |
| Charge | `daily_battery_charge_kwh` | "X.XX" |
| Vente | `daily_energy_sold_kwh` | "X.XX" |
| Achat | `daily_energy_bought_kwh` | "X.XX" |

---

### 7.8 Page 4: Monthly Financial Balance

**Section 1: Explanation Box**

```
L'économie panneaux représente l'argent économisé en utilisant la production des 
panneaux pour sa consommation de jour.

L'économie batterie représente l'argent économisé grâce à l'énergie stockée dans 
la batterie qui sera utilisée pour la consommation de nuit. Le calcul tient compte 
du coût d'utilisation de la batterie.

La vente correspond aux bénéfices engrangés en revendant le surplus de production.

L'achat est le montant à payer pour la partie de la consommation qui n'est pas 
couverte par la production.

Le bilan est la différence entre le montant à payer pour l'achat et le profit de la revente.
```

**Section 2: Financial Table**

| Column | Source | Format |
|--------|--------|--------|
| Mois | Month name | French |
| Économie panneaux | `panel_savings` | "X.XX €" |
| Économie batterie | `battery_savings` | "X.XX €" |
| Vente | `sale_revenue` | "X.XX €" |
| Achat | `purchase_cost` | "X.XX €" |
| Bilan | `net_balance` | "X.XX €" with color indicator |

**Section 3: Production vs Consumption Chart**

| Element | Source |
|---------|--------|
| Chart Image | `pv.simulation.chart_production_consumption` |
| Type | Stacked/grouped bar chart |

---

### 7.9 Page 5: Annual Summary

**Layout:** Icon-based grid with values

**Production Block:**

| Label | Source | Format |
|-------|--------|--------|
| Totale | `annual_production_calc_kwh` | "XXXXX.XX kWh" |

**Consumption Block:**

| Label | Source | Format |
|-------|--------|--------|
| Jour | `annual_day_consumption_kwh` | "XXXXX.XX kWh" |
| Nuit | `annual_night_consumption_kwh` | "XXXXX.XX kWh" |
| Totale | `annual_consumption_kwh` | "XXXXX.XX kWh" |

**Auto Consumption Block:**

| Label | Source | Format |
|-------|--------|--------|
| Consommé la journée | `annual_day_autoconsumption_kwh` | "XXXXX.XX kWh" |
| Stocké dans la batterie | `annual_battery_charge_kwh` | "XXXXX.XX kWh" |
| Total | `annual_autoconsumption_kwh` | "XXXXX.XX kWh" |

**Economies Block:**

| Label | Source | Format |
|-------|--------|--------|
| Liées aux panneaux | `total_panel_savings` | "XXXX.XX €" |
| Liées à la batterie | `total_battery_savings` | "XXXX.XX €" |
| Liées à la revente | `total_sale_revenue` | "XXX.XX €" |
| Total économies | `total_savings` | "XXXX.XX €" (highlighted) |
| Achat | `total_purchase_cost` | "XXXX.XX €" |

**Charts:**

| Element | Source |
|---------|--------|
| Annual Bar Chart | `pv.simulation.chart_annual_bar` |
| Annual Donut Chart | `pv.simulation.chart_annual_donut` |

---

### 7.10 Page 6: Selected Materials

**Table Columns:**

| Column | Source | Format |
|--------|--------|--------|
| ID | `sale.order.line.product_id.default_code` | Product reference |
| Image | `sale.order.line.product_id.image_128` | 50×50px thumbnail |
| Description | `sale.order.line.name` | Product name |
| Prix unit HT | `sale.order.line.price_unit` | "X €" |
| Quantité | `sale.order.line.product_uom_qty` | Integer |
| TVA | `sale.order.line.tax_id` | "X %" or "0" |
| Total TTC | `sale.order.line.price_total` | "X €" |

**Totals:**

| Label | Source | Format |
|-------|--------|--------|
| TOTAL HT | `sale.order.amount_untaxed` | "XXXXX €" |
| TVA | `sale.order.amount_tax` | "X %" |
| TOTAL TTC | `sale.order.amount_total` | "XXXXX €" (bold) |

---

## 8. Chart Specifications

### 8.1 Technical Approach

**Method:** Server-side rendering using **matplotlib**

**Rationale:**
- QWeb PDF (wkhtmltopdf) has limited JavaScript support
- Pre-rendered PNG images ensure consistent output
- No external dependencies at render time

### 8.2 Chart 1: Monthly Daily Production

| Property | Value |
|----------|-------|
| Type | Vertical Bar Chart |
| X-Axis | Months (J, F, M, A, M, J, J, A, S, O, N, D) |
| Y-Axis | Daily Production (kWh) |
| Bar Color | #8BC34A (Green) |
| Data Labels | Above each bar, 1 decimal place |
| Size | 500×300px |
| Background | White or transparent |

### 8.3 Chart 2: Production vs Consumption

| Property | Value |
|----------|-------|
| Type | Grouped/Stacked Bar Chart |
| X-Axis | Month names (French, full) |
| Series 1 | Production quotidienne (#8BC34A) |
| Series 2 | Consommation de jour (Light gray) |
| Series 3 | Consommation de nuit (Dark gray) |
| Series 4 | Revente (Light green) |
| Series 5 | Achat (Red, negative values below axis) |
| Size | 700×350px |

### 8.4 Chart 3: Annual Balance Bar

| Property | Value |
|----------|-------|
| Type | Vertical Bar Chart |
| Categories | Production, Autoconsommation, Vente, Achat |
| Values | Annual kWh totals |
| Colors | Green, Blue, Light green, Red |
| Size | 300×250px |

### 8.5 Chart 4: Annual Donut

| Property | Value |
|----------|-------|
| Type | Donut/Ring Chart |
| Segments | Production, Autoconsommation, Vente, Achat, Consommation |
| Colors | Distinct palette |
| Labels | Values as callouts or legend |
| Size | 300×300px |

### 8.6 Chart Generation Code Structure

```python
def _generate_charts(self):
    """Generate all chart images for the simulation."""
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import io
    import base64
    
    for record in self:
        # Chart 1: Monthly production
        record.chart_monthly_production = record._generate_monthly_production_chart()
        
        # Chart 2: Production vs consumption
        record.chart_production_consumption = record._generate_prod_cons_chart()
        
        # Chart 3: Annual bar
        record.chart_annual_bar = record._generate_annual_bar_chart()
        
        # Chart 4: Annual donut
        record.chart_annual_donut = record._generate_annual_donut_chart()

def _generate_monthly_production_chart(self):
    import matplotlib.pyplot as plt
    import io
    import base64
    
    fig, ax = plt.subplots(figsize=(6, 3.5))
    months = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
    values = [r.daily_production_kwh for r in self.monthly_result_ids.sorted('month')]
    
    bars = ax.bar(months, values, color='#8BC34A')
    ax.set_ylabel('kWh')
    
    # Add value labels
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{val:.1f}', ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    
    return base64.b64encode(buffer.getvalue())
```

---

## 9. Formatting Standards

### 9.1 Currency Display

| Context | Format | Example |
|---------|--------|---------|
| Financial values | `{value:,.2f} €` | "337.91 €" |
| Zero values | `0.00 €` | "0.00 €" |
| Negative (rare) | `-{value:,.2f} €` | "-15.43 €" |

### 9.2 Energy Display

| Context | Format | Example |
|---------|--------|---------|
| kWh values | `{value:,.2f} kWh` | "30,534.38 kWh" |
| Daily kWh | `{value:.2f} kWh` | "42.61 kWh" |
| Power (Wc) | `{value:,.0f}Wc` | "31,500Wc" |

### 9.3 Angles

| Context | Format | Example |
|---------|--------|---------|
| Orientation | `{value:.0f}°` | "-15°" |
| Inclination | `{value:.0f}°` | "30°" |

### 9.4 Percentages

| Context | Format | Example |
|---------|--------|---------|
| Tax rate | `{value:.0f} %` | "21 %" |
| Profile % | `{value:.2f}%` | "12.41%" |

### 9.5 Locale Settings

- Primary: French (Belgium) - `fr_BE`
- Decimal separator: `.` (period)
- Thousands separator: `,` (comma) or space
- Currency symbol: `€` (after value with space)

---

## 10. Color Scheme

### 10.1 Brand Colors

| Usage | Color Name | Hex Code |
|-------|------------|----------|
| Primary | Bright Green | #8BC34A |
| Secondary | Dark Green | #4A7C23 |
| Accent | Light Green | #C5E1A5 |
| Text | Dark Gray | #333333 |
| Background | White | #FFFFFF |

### 10.2 Financial Indicators

| Value Type | Color | Hex Code |
|------------|-------|----------|
| Positive (savings) | Green | #43A047 |
| Negative (cost) | Red | #E53935 |
| Neutral | Gray | #757575 |

### 10.3 Chart Colors

| Series | Hex Code |
|--------|----------|
| Production | #8BC34A |
| Day Consumption | #9E9E9E |
| Night Consumption | #616161 |
| Sale/Export | #C5E1A5 |
| Purchase/Import | #E53935 |
| Autoconsumption | #2196F3 |

---

## 11. Icons

### 11.1 Required Icons

| Icon Purpose | Usage Location |
|--------------|----------------|
| Solar panel | Annual summary - Production |
| Sun | Day consumption |
| Moon | Night consumption |
| Calendar | Total values |
| Battery | Battery storage |
| Piggy bank | Savings |
| Euro symbol | Financial values |
| House with lightning | Autoconsumption |
| Power grid | Grid purchase/sale |
| Location pin | Installation address |
| Email | Footer |
| Phone | Footer |

### 11.2 Implementation

- **Option 1:** SVG inline in QWeb templates
- **Option 2:** PNG files in `static/src/img/`
- **Option 3:** Font Awesome icons (if supported)

---

## 12. Security

### 12.1 Access Groups

| Group | Technical Name | Description |
|-------|----------------|-------------|
| User | `pv_simulation.group_user` | Sales users |
| Manager | `pv_simulation.group_manager` | Read-only access |
| Admin | `pv_simulation.group_admin` | Full configuration access |

### 12.2 Model Access Rights

| Model | User | Manager | Admin |
|-------|------|---------|-------|
| pv.simulation | CRUD | R | CRUD |
| pv.monthly.result | CRUD | R | CRUD |
| pv.consumption.profile | R | R | CRUD |
| pv.production.profile | R | R | CRUD |
| pv.battery.config | R | R | CRUD |
| pv.tariff.profile | R | R | CRUD |

### 12.3 Record Rules

```xml
<!-- Users can only see simulations linked to their sales team quotations -->
<record id="pv_simulation_rule_user" model="ir.rule">
    <field name="name">PV Simulation: Sales Team</field>
    <field name="model_id" ref="model_pv_simulation"/>
    <field name="domain_force">[('sale_order_id.team_id', 'in', user.sale_team_ids.ids)]</field>
    <field name="groups" eval="[(4, ref('pv_simulation.group_user'))]"/>
</record>
```

---

## 13. Demo Data

### 13.1 Default Production Profile (Belgium)

```python
{
    'name': 'Profil Standard Belgique',
    'january_pct': 3.62,
    'february_pct': 4.55,
    'march_pct': 8.47,
    'april_pct': 11.60,
    'may_pct': 12.16,
    'june_pct': 12.41,
    'july_pct': 12.44,
    'august_pct': 11.18,
    'september_pct': 9.60,
    'october_pct': 7.05,
    'november_pct': 3.92,
    'december_pct': 3.00,  # Adjusted to sum to 100%
}
```

### 13.2 Default Consumption Profile

```python
{
    'name': 'Ménage Standard',
    'annual_consumption_kwh': 29500.0,
    'daily_day_consumption_kwh': 39.33,
    'daily_night_consumption_kwh': 42.61,
}
```

### 13.3 Default Battery Configuration

```python
{
    'name': 'Pylontech US5000 38.4 kWh',
    'capacity_kwh': 38.4,
    'usable_ratio': 0.95,
    'max_daily_charge_kwh': 39.6,
    'efficiency': 0.95,
    'cost_per_kwh': 0.02,
}
```

### 13.4 Default Tariff Profile

```python
{
    'name': 'Tarif Standard Belgique 2024',
    'purchase_price_kwh': 0.25,
    'feed_in_tariff_kwh': 0.07,
    'currency_id': ref('base.EUR'),
}
```

---

## 14. Technical Constraints

- **Odoo Version:** 14.0+ (compatible with 15.0, 16.0, 17.0)
- **Python:** 3.8+
- **Dependencies:** matplotlib (for charts)
- **Deterministic:** All calculations must be reproducible
- **Unit-testable:** Compute methods must be testable in isolation
- **No external API:** No runtime dependency on external services

---

## 15. Module Structure

```
pv_simulation/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── res_company.py
│   ├── pv_simulation.py
│   ├── pv_monthly_result.py
│   ├── pv_consumption_profile.py
│   ├── pv_production_profile.py
│   ├── pv_battery_config.py
│   ├── pv_tariff_profile.py
│   └── sale_order.py
├── views/
│   ├── res_company_views.xml
│   ├── pv_simulation_views.xml
│   ├── pv_profile_views.xml
│   ├── sale_order_views.xml
│   └── menu_views.xml
├── report/
│   ├── pv_simulation_report.xml
│   ├── pv_simulation_templates.xml
│   └── pv_simulation_templates_pages.xml
├── security/
│   ├── pv_simulation_security.xml
│   └── ir.model.access.csv
├── data/
│   ├── pv_production_profile_data.xml
│   ├── pv_consumption_profile_data.xml
│   ├── pv_battery_config_data.xml
│   └── pv_tariff_profile_data.xml
├── static/
│   └── src/
│       └── img/
│           ├── icon_solar.png
│           ├── icon_battery.png
│           ├── icon_sun.png
│           ├── icon_moon.png
│           └── ... (other icons)
└── tests/
    ├── __init__.py
    ├── test_calculations.py
    └── test_simulation.py
```

---

## 16. Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Custom module | `pv_simulation` Odoo module | Required |
| Data models | All 7 models with fields | Required |
| Views | Form, tree, search views | Required |
| Access rules | Security groups and rules | Required |
| QWeb PDF report | 6-page report template | Required |
| Chart generation | matplotlib integration | Required |
| Demo data | Default profiles | Required |
| Static assets | Icons and images | Required |
| Company config | Branding fields on res.company | Required |
| Documentation | Installation and usage guide | Required |
| Unit tests | Calculation validation tests | Required |

---

## 17. Success Criteria

1. ✅ All calculations match Excel/PDF reference exactly
2. ✅ Fully reproducible and deterministic results
3. ✅ Clear separation of inputs vs computed results
4. ✅ Extendable architecture for future enhancements
5. ✅ PDF visual output matches reference layout
6. ✅ All charts render correctly in PDF
7. ✅ Company branding properly displayed
8. ✅ Currency and number formatting consistent
9. ✅ Demo data produces valid simulation matching reference
10. ✅ All unit tests pass

---

## Appendix A: Reference Data Validation

Values extracted from sample PDF for testing:

### System Configuration
| Parameter | Value |
|-----------|-------|
| Address | RUE DE CORDEMONT 38 B - 4450 SLINS |
| Panel Power | 31,500 Wc |
| Orientation | -15° |
| Inclination | 30° |
| Annual Production | 30,534.38 kWh |

### Consumption Profile
| Parameter | Value |
|-----------|-------|
| Monthly Consumption | 2,458.33 kWh |
| Daily Day Consumption | 39.33 kWh |
| Daily Night Consumption | 42.61 kWh |

### Battery Configuration
| Parameter | Value |
|-----------|-------|
| Model | Pylontech US5000 |
| Capacity | 38.4 kWh |
| Max Daily Charge | 39.60 kWh |

### Annual Summary (Expected Results)
| Metric | Value |
|--------|-------|
| Total Production | 30,534.38 kWh |
| Day Consumption | 14,158.8 kWh |
| Night Consumption | 15,339.6 kWh |
| Total Consumption | 29,499.96 kWh |
| Day Autoconsumption | 13,816.74 kWh |
| Battery Storage | 9,514.38 kWh |
| Total Autoconsumption | 23,331.12 kWh |
| Energy Sold | 7,203.26 kWh |
| Panel Savings | 3,454.14 € |
| Battery Savings | 2,318.53 € |
| Sale Revenue | 504.23 € |
| Total Savings | 6,276.90 € |

### Materials
| Product | Unit Price | Qty | Total |
|---------|------------|-----|-------|
| QN SOLAR 420Wc Panel | 475 € | 75 | 35,625 € |
| Sofar Solar 20 kVA Inverter | 8,160 € | 1 | 8,160 € |
| Pylontech US5000 38.4 kWh | 35,890 € | 1 | 35,890 € |
| **TOTAL TTC** | | | **79,675 €** |

---

## Appendix B: Monthly Reference Data

| Month | Production (kWh) | Daily Prod | Charge | Vente | Achat |
|-------|------------------|------------|--------|-------|-------|
| January | 1,106.58 | 36.89 | 0.00 | 0.00 | 45.05 |
| February | 1,388.51 | 46.28 | 6.95 | 0.00 | 35.66 |
| March | 2,588.29 | 86.28 | 39.60 | 7.35 | 3.01 |
| April | 3,540.33 | 118.01 | 39.60 | 39.08 | 3.01 |
| May | 3,713.90 | 123.80 | 39.60 | 44.87 | 3.01 |
| June | 3,790.61 | 126.35 | 39.60 | 47.42 | 3.01 |
| July | 3,800.34 | 126.68 | 39.60 | 47.75 | 3.01 |
| August | 3,414.46 | 113.82 | 39.60 | 34.89 | 3.01 |
| September | 2,930.63 | 97.69 | 39.60 | 18.76 | 3.01 |
| October | 2,152.13 | 71.74 | 32.41 | 0.00 | 10.20 |
| November | 1,197.44 | 39.91 | 0.58 | 0.00 | 42.03 |
| December | 911.16 | 30.37 | 0.00 | 0.00 | 51.57 |

---

*End of Complete Specification v2.0*
