#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client Simulation Comparison: BOURGOIS Michel
==============================================

Standalone script that replicates the pv.simulation energy balance logic
and compares simulated results against actual monitoring data from FusionSolar.

Client: BOURGOIS Michel
Location: Foy-le-Grand, Rue des Corbeaux, Belgium
    Latitude: 50°39'40.6" N → 50.6613°
    Longitude: 4°40'31.9" E → 4.6755°
System: 12× JA Solar Biface 455 Wc = 5,460 Wc
Battery: SUN PLUS 5 kW (5 kWh)
Type: PV + Grid + Consumption + Battery

Usage:
    python3 client_simulation_bourgois.py
"""

import calendar
from dataclasses import dataclass

# ============================================================
# CLIENT SYSTEM PARAMETERS (from screenshots & user input)
# ============================================================

CLIENT_NAME = "BOURGOIS Michel"

# PV System
TOTAL_PV_POWER_WC = 5460          # 12 panels × 455 Wc
NUM_PANELS = 12
PANEL_UNIT_POWER_WC = 455         # JA Solar Biface 455 Wc

# Location
LATITUDE = 50.6613                # 50°39'40.6" N
LONGITUDE = 4.6755                # 4°40'31.9" E

# Battery
BATTERY_CAPACITY_KWH = 5.0       # SUN PLUS 5 kW
BATTERY_EFFICIENCY_PCT = 95.0     # Typical Li-ion (assumed)
BATTERY_USABLE_RATIO = 0.95       # Typical usable ratio

# Tariff (Belgian Standard 2024)
PURCHASE_PRICE_KWH = 0.31         # €/kWh grid purchase
FEED_IN_TARIFF_KWH = 0.21         # €/kWh grid sale
BATTERY_COST_KWH = 0.02           # €/kWh battery degradation

# Production Profile — Belgian Standard (monthly % of annual production)
BELGIAN_PRODUCTION_PROFILE = {
    1: 3.62, 2: 4.55, 3: 8.47, 4: 11.60, 5: 12.16, 6: 12.41,
    7: 12.44, 8: 11.18, 9: 9.60, 10: 7.05, 11: 3.92, 12: 3.00,
}

# Orientation/Tilt — Unknown, using typical Belgian defaults
ORIENTATION_DEG = 0    # South
TILT_DEG = 35          # Typical Belgian residential


# ============================================================
# ACTUAL MONITORING DATA (from FusionSolar screenshots)
# ============================================================
# Note: Consumption meter was not active until ~Aug 2025
# Months with "--" consumption are marked as None

@dataclass
class MonthlyActual:
    """Actual monthly data from FusionSolar monitoring."""
    year: int
    month: int
    production_kwh: float
    consumption_kwh: float | None    # None = meter not active
    grid_inject_kwh: float
    grid_purchase_kwh: float
    battery_charge_kwh: float
    battery_discharge_kwh: float

    @property
    def days(self):
        return calendar.monthrange(self.year, self.month)[1]

    @property
    def label(self):
        return f"{self.year}/{self.month:02d}"


ACTUAL_DATA = [
    # 2025 — Annual total: Production 2.37 MWh, Consumption 920.3 kWh (partial)
    MonthlyActual(2025, 6,  233.8, None,  184.5,  25.7,  22.5, 17.9),
    MonthlyActual(2025, 7,  632.2, None,  491.2,   2.9,  68.2, 44.6),
    MonthlyActual(2025, 8,  700.5,  83.9, 553.0,   0.8,  78.1, 44.5),
    MonthlyActual(2025, 9,  441.7,  85.0, 303.4,   2.0,  91.5, 53.0),
    MonthlyActual(2025, 10, 189.2, 132.6,  50.7,  43.5, 112.5, 74.2),
    MonthlyActual(2025, 11,  97.5, 214.7,   6.1, 167.6,  77.7, 37.3),
    MonthlyActual(2025, 12,  71.4, 270.9,   0.6, 240.9,  62.9, 22.0),
    # 2026 — YTD: Production 437.5 kWh, Consumption 581.8 kWh
    MonthlyActual(2026, 1,   73.9, 331.0,   0.7, 299.6,  62.8, 24.6),
    MonthlyActual(2026, 2,  155.2, 181.4,  36.0, 109.5, 102.2, 62.2),
    # 2026/03 partial — not included (data up to 2026/03/16)
]


# ============================================================
# SIMULATION ENGINE (mirrors pv_simulation.py logic)
# ============================================================

@dataclass
class MonthlySimResult:
    """Simulated monthly energy balance result."""
    month: int
    days: int
    # Daily averages
    daily_production_kwh: float
    daily_day_consumption_kwh: float
    daily_night_consumption_kwh: float
    daily_surplus_pv_kwh: float
    daily_day_autoconsumption_kwh: float
    daily_battery_charge_kwh: float
    daily_energy_sold_kwh: float
    daily_energy_bought_kwh: float
    # Monthly totals
    monthly_production_kwh: float
    monthly_consumption_kwh: float
    monthly_battery_charge_kwh: float
    monthly_energy_sold_kwh: float
    monthly_energy_bought_kwh: float
    monthly_autoconsumption_kwh: float
    # Financial
    panel_savings: float
    battery_savings: float
    sale_revenue: float
    purchase_cost: float
    net_balance: float


def compute_daily_balance(
    monthly_production: dict[int, float],
    monthly_consumption: dict[int, float],
    day_night_ratio: float = 0.5,
    battery_capacity_kwh: float = 5.0,
    battery_efficiency_pct: float = 95.0,
    p_buy: float = 0.31,
    p_sell: float = 0.21,
    p_batt: float = 0.02,
    year: int = 2025,
) -> list[MonthlySimResult]:
    """
    Compute the energy balance for 12 months.

    Replicates the logic from pv_simulation.py:action_compute_daily_balance()

    Args:
        monthly_production: {month_number: production_kwh} for months 1-12
        monthly_consumption: {month_number: consumption_kwh} for months 1-12
        day_night_ratio: fraction of consumption during day (6h-18h)
        battery_capacity_kwh: usable battery capacity
        battery_efficiency_pct: round-trip efficiency as percentage
        p_buy: grid purchase price €/kWh
        p_sell: feed-in tariff €/kWh
        p_batt: battery degradation cost €/kWh
        year: year for days-in-month calculation
    """
    cap_bat = battery_capacity_kwh
    ren_bat = battery_efficiency_pct / 100.0
    cap_bat_effective = cap_bat * ren_bat

    results = []
    cap_debut_bat = 0.0  # Battery starts empty

    for month in range(1, 13):
        days = calendar.monthrange(year, month)[1]
        prod_monthly = monthly_production.get(month, 0.0)
        cons_monthly = monthly_consumption.get(month, 0.0)

        prod = prod_monthly / days  # daily production
        conso_jour = (cons_monthly * day_night_ratio) / days  # daily day consumption
        conso_nuit = (cons_monthly * (1 - day_night_ratio)) / days  # daily night consumption

        # Energy balance (same formulas as pv_simulation.py)
        surplus_pv = max(0.0, prod - conso_jour)
        autocons_jour = min(prod, conso_jour)
        charge = min(surplus_pv, cap_bat_effective) if cap_bat > 0 else 0.0
        vente = surplus_pv - charge
        energie_bat_nuit = min(cap_debut_bat + charge, cap_bat_effective) if cap_bat > 0 else 0.0
        achat = max(0.0, conso_nuit - energie_bat_nuit)

        # Financial
        eco_panneaux = round(autocons_jour * days * p_buy, 2)
        revenu_vente = round(vente * days * p_sell, 2)
        batt_use = min(energie_bat_nuit, conso_nuit) if cap_bat > 0 else 0.0
        eco_batterie = round(batt_use * days * (p_buy - p_batt), 2)
        cout_achat = round(achat * days * p_buy, 2)

        results.append(MonthlySimResult(
            month=month,
            days=days,
            daily_production_kwh=round(prod, 2),
            daily_day_consumption_kwh=round(conso_jour, 2),
            daily_night_consumption_kwh=round(conso_nuit, 2),
            daily_surplus_pv_kwh=round(surplus_pv, 2),
            daily_day_autoconsumption_kwh=round(autocons_jour, 2),
            daily_battery_charge_kwh=round(charge, 2),
            daily_energy_sold_kwh=round(vente, 2),
            daily_energy_bought_kwh=round(achat, 2),
            monthly_production_kwh=round(prod_monthly, 2),
            monthly_consumption_kwh=round(cons_monthly, 2),
            monthly_battery_charge_kwh=round(charge * days, 2),
            monthly_energy_sold_kwh=round(vente * days, 2),
            monthly_energy_bought_kwh=round(achat * days, 2),
            monthly_autoconsumption_kwh=round((autocons_jour + charge) * days, 2),
            panel_savings=eco_panneaux,
            battery_savings=eco_batterie,
            sale_revenue=revenu_vente,
            purchase_cost=cout_achat,
            net_balance=cout_achat - revenu_vente,
        ))

        # CapDebutBat for next month
        cap_debut_bat = max(0.0, min(cap_bat_effective, cap_debut_bat + charge - conso_nuit))

    return results


def estimate_annual_production(actual_data: list[MonthlyActual]) -> float:
    """
    Estimate annual production from partial actual data using the Belgian production profile.

    For each month with actual data, calculate the implied annual production,
    then average across months for a better estimate.
    """
    estimates = []
    for actual in actual_data:
        pct = BELGIAN_PRODUCTION_PROFILE.get(actual.month, 0)
        if pct > 0 and actual.production_kwh > 0:
            implied_annual = actual.production_kwh / (pct / 100.0)
            estimates.append(implied_annual)

    if estimates:
        return sum(estimates) / len(estimates)
    return 0.0


def estimate_monthly_consumption(actual_data: list[MonthlyActual]) -> dict[int, float]:
    """
    Estimate monthly consumption for all 12 months.

    Uses actual data where available; for missing months, uses the average
    of available months (simple approach — could be improved with seasonal patterns).
    """
    consumption_by_month = {}
    for actual in actual_data:
        if actual.consumption_kwh is not None:
            consumption_by_month[actual.month] = actual.consumption_kwh

    # For months without data, use average of known months
    if consumption_by_month:
        avg = sum(consumption_by_month.values()) / len(consumption_by_month)
    else:
        avg = 150.0  # fallback default

    result = {}
    for m in range(1, 13):
        result[m] = consumption_by_month.get(m, avg)

    return result


# ============================================================
# COMPARISON & REPORTING
# ============================================================

def compare_simulation_vs_actual(
    sim_results: list[MonthlySimResult],
    actual_data: list[MonthlyActual],
):
    """Print a detailed comparison table between simulation and actual data."""

    print("=" * 120)
    print(f"  SIMULATION vs ACTUAL COMPARISON — {CLIENT_NAME}")
    print(f"  System: {NUM_PANELS}× JA Solar Biface {PANEL_UNIT_POWER_WC} Wc = {TOTAL_PV_POWER_WC} Wc")
    print(f"  Battery: SUN PLUS {BATTERY_CAPACITY_KWH} kWh | Efficiency: {BATTERY_EFFICIENCY_PCT}%")
    print(f"  Location: {LATITUDE}°N, {LONGITUDE}°E")
    print("=" * 120)

    # Build lookup: month -> actual
    actual_by_month = {(a.year, a.month): a for a in actual_data}

    # Headers
    print(f"\n{'Month':>8} | {'Metric':>20} | {'Simulated':>10} | {'Actual':>10} | {'Delta':>10} | {'Delta%':>8}")
    print("-" * 85)

    metrics = [
        ("Production", "monthly_production_kwh", "production_kwh"),
        ("Grid Inject", "monthly_energy_sold_kwh", "grid_inject_kwh"),
        ("Grid Purchase", "monthly_energy_bought_kwh", "grid_purchase_kwh"),
        ("Batt Charge", "monthly_battery_charge_kwh", "battery_charge_kwh"),
    ]

    total_deltas = {m[0]: [] for m in metrics}

    for actual in actual_data:
        # Find matching simulation month
        sim = next((s for s in sim_results if s.month == actual.month), None)
        if not sim:
            continue

        for label, sim_attr, act_attr in metrics:
            sim_val = getattr(sim, sim_attr)
            act_val = getattr(actual, act_attr)
            if act_val is None:
                continue

            delta = sim_val - act_val
            delta_pct = (delta / act_val * 100) if act_val != 0 else 0

            total_deltas[label].append((sim_val, act_val, delta))

            print(f"{actual.label:>8} | {label:>20} | {sim_val:>10.1f} | {act_val:>10.1f} | {delta:>+10.1f} | {delta_pct:>+7.1f}%")
        print("-" * 85)

    # Summary
    print(f"\n{'TOTALS':>8} | {'Metric':>20} | {'Sim Total':>10} | {'Act Total':>10} | {'Delta':>10} | {'Delta%':>8}")
    print("=" * 85)
    for label, deltas in total_deltas.items():
        if deltas:
            sim_total = sum(d[0] for d in deltas)
            act_total = sum(d[1] for d in deltas)
            delta_total = sim_total - act_total
            delta_pct = (delta_total / act_total * 100) if act_total != 0 else 0
            print(f"{'':>8} | {label:>20} | {sim_total:>10.1f} | {act_total:>10.1f} | {delta_total:>+10.1f} | {delta_pct:>+7.1f}%")


def print_simulation_summary(results: list[MonthlySimResult], annual_production: float):
    """Print the full simulation output."""
    print(f"\n{'=' * 100}")
    print(f"  SIMULATION OUTPUT — {CLIENT_NAME}")
    print(f"  Annual Production Estimate: {annual_production:.0f} kWh")
    print(f"{'=' * 100}")

    print(f"\n{'Month':>5} | {'Prod':>8} | {'Cons':>8} | {'AutoCons':>8} | {'BattChg':>8} | "
          f"{'Sold':>8} | {'Bought':>8} | {'PanelSav':>8} | {'BattSav':>8} | {'SaleRev':>8} | {'PurchCost':>9}")
    print("-" * 115)

    totals = {
        'prod': 0, 'cons': 0, 'autocons': 0, 'charge': 0,
        'sold': 0, 'bought': 0, 'panel_sav': 0, 'batt_sav': 0,
        'sale_rev': 0, 'purch_cost': 0,
    }

    month_names = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
                   'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

    for r in results:
        print(f"{month_names[r.month-1]:>5} | {r.monthly_production_kwh:>8.1f} | {r.monthly_consumption_kwh:>8.1f} | "
              f"{r.monthly_autoconsumption_kwh:>8.1f} | {r.monthly_battery_charge_kwh:>8.1f} | "
              f"{r.monthly_energy_sold_kwh:>8.1f} | {r.monthly_energy_bought_kwh:>8.1f} | "
              f"{r.panel_savings:>8.2f} | {r.battery_savings:>8.2f} | {r.sale_revenue:>8.2f} | {r.purchase_cost:>9.2f}")

        totals['prod'] += r.monthly_production_kwh
        totals['cons'] += r.monthly_consumption_kwh
        totals['autocons'] += r.monthly_autoconsumption_kwh
        totals['charge'] += r.monthly_battery_charge_kwh
        totals['sold'] += r.monthly_energy_sold_kwh
        totals['bought'] += r.monthly_energy_bought_kwh
        totals['panel_sav'] += r.panel_savings
        totals['batt_sav'] += r.battery_savings
        totals['sale_rev'] += r.sale_revenue
        totals['purch_cost'] += r.purchase_cost

    print("-" * 115)
    print(f"{'TOTAL':>5} | {totals['prod']:>8.1f} | {totals['cons']:>8.1f} | "
          f"{totals['autocons']:>8.1f} | {totals['charge']:>8.1f} | "
          f"{totals['sold']:>8.1f} | {totals['bought']:>8.1f} | "
          f"{totals['panel_sav']:>8.2f} | {totals['batt_sav']:>8.2f} | {totals['sale_rev']:>8.2f} | {totals['purch_cost']:>9.2f}")

    total_savings = totals['panel_sav'] + totals['batt_sav'] + totals['sale_rev']
    print(f"\n  Total savings (panels + battery + sale): €{total_savings:.2f}")
    print(f"  Total grid purchase cost: €{totals['purch_cost']:.2f}")
    print(f"  Net annual benefit: €{total_savings - totals['purch_cost']:.2f}")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"\n{'#' * 80}")
    print(f"#  BELGOGREEN PV SIMULATION — Client Comparison Tool")
    print(f"#  Client: {CLIENT_NAME}")
    print(f"{'#' * 80}\n")

    # Step 1: Estimate annual production from actual data
    annual_prod_estimate = estimate_annual_production(ACTUAL_DATA)
    print(f"Estimated annual production (from actual data + Belgian profile): {annual_prod_estimate:.0f} kWh")
    print(f"  (2025 actual total reported by FusionSolar: 2,370 kWh)")

    # Also use actual 2025 reported total for comparison
    annual_prod_actual_2025 = 2370.0

    # Step 2: Estimate monthly consumption
    monthly_consumption = estimate_monthly_consumption(ACTUAL_DATA)
    print(f"\nEstimated monthly consumption (kWh):")
    for m in range(1, 13):
        src = "actual" if any(a.month == m and a.consumption_kwh is not None for a in ACTUAL_DATA) else "estimated"
        print(f"  Month {m:>2}: {monthly_consumption[m]:>7.1f} kWh ({src})")

    # Step 3: Generate monthly production using Belgian profile + actual annual
    monthly_production_profile = {}
    for m in range(1, 13):
        monthly_production_profile[m] = annual_prod_actual_2025 * BELGIAN_PRODUCTION_PROFILE[m] / 100.0

    # Also build from actual data where available
    monthly_production_actual = {}
    for a in ACTUAL_DATA:
        if a.year == 2025:
            monthly_production_actual[a.month] = a.production_kwh
    # Fill missing months from profile
    for m in range(1, 13):
        if m not in monthly_production_actual:
            monthly_production_actual[m] = monthly_production_profile[m]

    # Step 4: Run simulation with profile-based production
    print(f"\n{'=' * 80}")
    print("SCENARIO 1: Using Belgian Standard Production Profile + actual 2025 annual (2370 kWh)")
    print(f"{'=' * 80}")

    sim_results_profile = compute_daily_balance(
        monthly_production=monthly_production_profile,
        monthly_consumption=monthly_consumption,
        day_night_ratio=0.5,
        battery_capacity_kwh=BATTERY_CAPACITY_KWH,
        battery_efficiency_pct=BATTERY_EFFICIENCY_PCT,
        p_buy=PURCHASE_PRICE_KWH,
        p_sell=FEED_IN_TARIFF_KWH,
        p_batt=BATTERY_COST_KWH,
        year=2025,
    )

    print_simulation_summary(sim_results_profile, annual_prod_actual_2025)
    compare_simulation_vs_actual(sim_results_profile, ACTUAL_DATA)

    # Step 5: Run simulation with actual monthly production data
    print(f"\n\n{'=' * 80}")
    print("SCENARIO 2: Using ACTUAL monthly production (where available)")
    print(f"{'=' * 80}")

    sim_results_actual = compute_daily_balance(
        monthly_production=monthly_production_actual,
        monthly_consumption=monthly_consumption,
        day_night_ratio=0.5,
        battery_capacity_kwh=BATTERY_CAPACITY_KWH,
        battery_efficiency_pct=BATTERY_EFFICIENCY_PCT,
        p_buy=PURCHASE_PRICE_KWH,
        p_sell=FEED_IN_TARIFF_KWH,
        p_batt=BATTERY_COST_KWH,
        year=2025,
    )

    print_simulation_summary(sim_results_actual, annual_prod_actual_2025)
    compare_simulation_vs_actual(sim_results_actual, ACTUAL_DATA)

    # Step 6: Key observations
    print(f"\n\n{'=' * 80}")
    print("KEY OBSERVATIONS")
    print(f"{'=' * 80}")
    print("""
    1. PRODUCTION: The Belgian Standard Profile distributes production evenly,
       but actual data shows higher summer peaks (Jul=632, Aug=700 kWh) than
       the profile predicts. The 5 kWp system with biface panels may over-perform
       the standard profile in summer months.

    2. BATTERY: The simulation uses a simplified daily model (charge from surplus,
       discharge at night). Actual battery behavior shows higher charge values
       than expected in some months (Oct: 112.5 kWh actual vs model prediction),
       suggesting the battery may charge/discharge multiple times per day.

    3. CONSUMPTION: Only available from Aug 2025 onwards. Shows strong seasonal
       pattern: low in summer (~85 kWh), high in winter (~270-331 kWh).
       The 50/50 day/night split is an assumption — real split may differ.

    4. DAY/NIGHT RATIO: This is a key parameter affecting self-consumption.
       Consider testing ratios from 0.3 to 0.7 to find best match with actual data.
    """)


if __name__ == "__main__":
    main()
