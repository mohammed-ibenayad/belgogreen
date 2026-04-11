# Client Reference Data: BOURGOIS Michel

## System Specs

| Parameter | Value |
|-----------|-------|
| Panels | 12× JA Solar Biface 455 Wc = **5,460 Wc** |
| Battery | SUN PLUS 5 kW (**5 kWh**) |
| Location | Foy-le-Grand, Rue des Corbeaux, Belgium |
| Coordinates | Lat **50.6613°** N / Lon **4.6755°** E |
| Orientation/Tilt | Unknown → assume South, 35° |
| Install date | ~June 2025 |
| Monitoring | FusionSolar |

---

## Data Sources

- **Actual (FusionSolar):** Months with real monitoring data from the inverter/meter. Production available from Jun 2025. Consumption meter only active from Aug 2025.
- **2026 proxy:** Jan & Feb 2026 actual FusionSolar data used as proxy for Jan & Feb 2025 (system wasn't installed yet in early 2025).
- **Estimated production:** Mar/Apr/May derived from Belgian Standard Production Profile applied to an estimated annual total of ~2,600 kWh (calculated by averaging the implied annual totals from the Oct–Feb actual months, which are least affected by biface over-performance).
- **Estimated consumption:** Jun & Jul interpolated from seasonal curve (Jan peak 331 kWh → Aug/Sep trough ~85 kWh). Mar/Apr/May estimated from same seasonal interpolation.

---

## Complete 2025 Monthly Data (12 months)

### Production & Consumption (Simulation Inputs)

| Month | Prod (kWh) | Cons (kWh) | Prod Source | Cons Source |
|-------|-----------|-----------|-------------|-------------|
| Jan | 73.9 | 331.0 | 2026 proxy (FusionSolar Jan 2026) | 2026 proxy (FusionSolar Jan 2026) |
| Feb | 155.2 | 181.4 | 2026 proxy (FusionSolar Feb 2026) | 2026 proxy (FusionSolar Feb 2026) |
| Mar | 220.2 | 200.0 | **Estimated** (8.47% × 2600) | **Estimated** (seasonal interpolation) |
| Apr | 301.6 | 160.0 | **Estimated** (11.60% × 2600) | **Estimated** (seasonal interpolation) |
| May | 316.2 | 120.0 | **Estimated** (12.16% × 2600) | **Estimated** (seasonal interpolation) |
| Jun | 233.8 | 90.0 | Actual (FusionSolar) | **Estimated** (meter not active) |
| Jul | 632.2 | 85.0 | Actual (FusionSolar) | **Estimated** (meter not active) |
| Aug | 700.5 | 83.9 | Actual (FusionSolar) | Actual (FusionSolar) |
| Sep | 441.7 | 85.0 | Actual (FusionSolar) | Actual (FusionSolar) |
| Oct | 189.2 | 132.6 | Actual (FusionSolar) | Actual (FusionSolar) |
| Nov | 97.5 | 214.7 | Actual (FusionSolar) | Actual (FusionSolar) |
| Dec | 71.4 | 270.9 | Actual (FusionSolar) | Actual (FusionSolar) |
| **TOTAL** | **3,433.4** | **1,954.5** | | |

### Grid & Battery (Comparison Outputs)

These are the actual FusionSolar readings to compare against what the app simulation produces.

| Month | Grid Inject (kWh) | Grid Purchase (kWh) | Batt Charge (kWh) | Batt Discharge (kWh) | Source |
|-------|-------------------|---------------------|--------------------|-----------------------|--------|
| Jan | 0.7 | 299.6 | 62.8 | 24.6 | 2026 proxy |
| Feb | 36.0 | 109.5 | 102.2 | 62.2 | 2026 proxy |
| Mar | — | — | — | — | No data |
| Apr | — | — | — | — | No data |
| May | — | — | — | — | No data |
| Jun | 184.5 | 25.7 | 22.5 | 17.9 | Actual |
| Jul | 491.2 | 2.9 | 68.2 | 44.6 | Actual |
| Aug | 553.0 | 0.8 | 78.1 | 44.5 | Actual |
| Sep | 303.4 | 2.0 | 91.5 | 53.0 | Actual |
| Oct | 50.7 | 43.5 | 112.5 | 74.2 | Actual |
| Nov | 6.1 | 167.6 | 77.7 | 37.3 | Actual |
| Dec | 0.6 | 240.9 | 62.9 | 22.0 | Actual |

> **Note:** Mar/Apr/May have no grid or battery actuals — the system wasn't installed yet and no 2026 data exists for those months. Simulation results for those months cannot be validated.

---

## How to Use This Reference

1. **Run the app simulation** for client BOURGOIS with the inputs from the "Production & Consumption" table above
2. **Compare the app's output** (grid inject, grid purchase, battery charge/discharge) against the "Grid & Battery" table
3. **Focus comparison on months with actual data** (Aug–Dec 2025 have full actuals; Jan/Feb are 2026 proxies; Jun/Jul have production actuals but estimated consumption)
4. **Key metrics to compare:** Grid Inject, Grid Purchase, Battery Charge — these reveal how well the simulation models self-consumption and battery behavior

---

## Estimation Methodology Notes

### Annual production estimate: ~2,600 kWh
Derived from winter months (least affected by biface panel over-performance):
- Oct: 189.2 / 7.05% = 2,683 kWh implied annual
- Nov: 97.5 / 3.92% = 2,488 kWh implied annual
- Dec: 71.4 / 3.00% = 2,380 kWh implied annual
- Jan (2026): 73.9 / 3.62% = 2,041 kWh implied annual
- Feb (2026): 155.2 / 4.55% = 3,411 kWh implied annual
- **Average: ~2,600 kWh**

> FusionSolar reported 2,370 kWh for 2025 but that only covers Jun–Dec (7 months). The full-year estimate is higher.

### Consumption seasonal pattern
Known data points: Jan=331, Feb=181, Aug=84, Sep=85, Oct=133, Nov=215, Dec=271.
Smooth interpolation: Mar≈200, Apr≈160, May≈120, Jun≈90, Jul≈85.
