# -*- coding: utf-8 -*-
"""Tests for :meth:`pv.simulation.action_compute_daily_balance`.

These tests bypass PVGIS entirely: they seed monthly results with known
daily production / consumption values and then assert the charge,
vente and achat outputs follow the formulas documented in the method's
docstring.
"""

from odoo.tests import tagged

from .common import PvSimulationTestBase


@tagged('post_install', '-at_install')
class TestEnergyBalance(PvSimulationTestBase):

    def _run_for_january(self, sim, prod_day, conso_day, conso_night):
        """Create a single January monthly result, run the balance, return it."""
        result = self._make_monthly_result(
            sim, month=1,
            prod_day=prod_day, conso_day=conso_day, conso_night=conso_night,
        )
        sim.action_compute_daily_balance()
        result.invalidate_recordset()
        return result

    def test_surplus_charges_battery_then_is_sold(self):
        """Production > day consumption: charge fills battery, rest is sold."""
        sim = self._make_simulation()
        # sanity: the fixture should give us a 10 kWh / 100% battery.
        self.assertEqual(sim.battery_capacity_kwh, 10.0)
        self.assertEqual(sim.battery_efficiency, 100.0)

        # 20 kWh produced, 12 kWh day, 5 kWh night.
        # surplus_pv = 20 - 12 = 8
        # charge = min(8, 10) = 8
        # vente = 8 - 8 = 0
        # energie_bat_nuit = min(0 + 8, 10) = 8
        # achat = max(0, 5 - 8) + max(0, 12 - 20) = 0
        result = self._run_for_january(sim, prod_day=20, conso_day=12, conso_night=5)
        self.assertAlmostEqual(result.daily_surplus_pv_kwh, 8.0, places=2)
        self.assertAlmostEqual(result.daily_day_autoconsumption_kwh, 12.0, places=2)
        self.assertAlmostEqual(result.daily_battery_charge_kwh, 8.0, places=2)
        self.assertAlmostEqual(result.daily_energy_sold_kwh, 0.0, places=2)
        self.assertAlmostEqual(result.daily_energy_bought_kwh, 0.0, places=2)

    def test_surplus_exceeds_battery_capacity_is_sold(self):
        """Excess production above battery capacity flows to grid as Vente."""
        sim = self._make_simulation()
        # 30 kWh produced, 10 kWh day, 4 kWh night.
        # surplus_pv = 20
        # charge = min(20, 10) = 10
        # vente = 20 - 10 = 10
        # energie_bat_nuit = min(0 + 10, 10) = 10
        # achat = max(0, 4 - 10) + max(0, 10 - 30) = 0
        result = self._run_for_january(sim, prod_day=30, conso_day=10, conso_night=4)
        self.assertAlmostEqual(result.daily_battery_charge_kwh, 10.0, places=2)
        self.assertAlmostEqual(result.daily_energy_sold_kwh, 10.0, places=2)
        self.assertAlmostEqual(result.daily_energy_bought_kwh, 0.0, places=2)

    def test_night_deficit_is_bought_from_grid(self):
        """Battery can't cover the night: the shortfall hits Achat."""
        sim = self._make_simulation()
        # 15 kWh produced, 10 kWh day, 12 kWh night.
        # surplus_pv = 5, charge = 5, vente = 0
        # energie_bat_nuit = min(0 + 5, 10) = 5
        # achat = max(0, 12 - 5) + max(0, 10 - 15) = 7 + 0 = 7
        result = self._run_for_january(sim, prod_day=15, conso_day=10, conso_night=12)
        self.assertAlmostEqual(result.daily_battery_charge_kwh, 5.0, places=2)
        self.assertAlmostEqual(result.daily_energy_sold_kwh, 0.0, places=2)
        self.assertAlmostEqual(result.daily_energy_bought_kwh, 7.0, places=2)

    def test_day_deficit_is_billed_via_new_achat_formula(self):
        """New Achat formula: daytime production shortfall is also billed."""
        sim = self._make_simulation()
        # 5 kWh produced, 10 kWh day, 4 kWh night.
        # surplus_pv = max(0, 5 - 10) = 0
        # charge = 0, vente = 0
        # energie_bat_nuit = 0
        # achat = max(0, 4 - 0) + max(0, 10 - 5) = 4 + 5 = 9
        result = self._run_for_january(sim, prod_day=5, conso_day=10, conso_night=4)
        self.assertAlmostEqual(result.daily_battery_charge_kwh, 0.0, places=2)
        self.assertAlmostEqual(result.daily_energy_sold_kwh, 0.0, places=2)
        self.assertAlmostEqual(result.daily_energy_bought_kwh, 9.0, places=2)

    def test_no_battery_means_no_charge(self):
        """Without a battery, Charge stays 0 and every deficit is billed."""
        # Drop the battery line from the sale order so the simulation's
        # computed battery_capacity_kwh is 0.
        self.sale_order.order_line.filtered(
            lambda l: l.product_id == self.battery_product
        ).unlink()
        sim = self._make_simulation()
        self.assertEqual(sim.battery_capacity_kwh, 0.0)

        # 20 kWh produced, 12 kWh day, 5 kWh night.
        # surplus_pv = 8, charge = 0 (no battery), vente = 8
        # energie_bat_nuit = 0
        # achat = max(0, 5 - 0) + max(0, 12 - 20) = 5
        result = self._run_for_january(sim, prod_day=20, conso_day=12, conso_night=5)
        self.assertAlmostEqual(result.daily_battery_charge_kwh, 0.0, places=2)
        self.assertAlmostEqual(result.daily_energy_sold_kwh, 8.0, places=2)
        self.assertAlmostEqual(result.daily_energy_bought_kwh, 5.0, places=2)

    def test_monthly_totals_multiply_by_days(self):
        """Monthly totals = daily value × days_in_month for each month."""
        sim = self._make_simulation()
        result = self._make_monthly_result(
            sim, month=1, prod_day=20, conso_day=12, conso_night=5,
        )
        sim.action_compute_daily_balance()
        result.invalidate_recordset()
        # January has 31 days; charge = 8/day; vente = 0/day.
        self.assertAlmostEqual(result.monthly_battery_charge_kwh, 8.0 * 31, places=2)
        self.assertAlmostEqual(result.monthly_energy_sold_kwh, 0.0, places=2)

    def test_financial_savings_reflect_autoconso_and_battery(self):
        """Panel savings = autoconso × days × P_buy; battery savings = usage × days × (P_buy − P_batt)."""
        sim = self._make_simulation()
        # 20 kWh produced, 12 kWh day, 5 kWh night, battery = 10 kWh.
        # autocons_jour = 12, charge = 8, batt_use = min(8, 5) = 5.
        # Jan has 31 days. P_buy = 0.30, P_batt = 0.02.
        # eco_panneaux = 12 × 31 × 0.30 = 111.60
        # eco_batterie = 5 × 31 × (0.30 − 0.02) = 43.40
        result = self._run_for_january(sim, prod_day=20, conso_day=12, conso_night=5)
        self.assertAlmostEqual(result.panel_savings, 111.60, places=2)
        self.assertAlmostEqual(result.battery_savings, 43.40, places=2)
