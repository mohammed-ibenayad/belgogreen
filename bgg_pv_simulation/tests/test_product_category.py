# -*- coding: utf-8 -*-
"""Tests for the panel/battery category detection helpers."""

from odoo.tests import tagged

from odoo.addons.bgg_pv_simulation.models.product_template import (
    _is_battery_category,
    _is_panel_category,
)

from .common import PvSimulationTestBase


@tagged('post_install', '-at_install')
class TestProductCategoryHelpers(PvSimulationTestBase):

    def test_panel_product_is_detected(self):
        self.assertTrue(_is_panel_category(self.panel_product))
        self.assertFalse(_is_battery_category(self.panel_product))

    def test_battery_product_is_detected(self):
        self.assertTrue(_is_battery_category(self.battery_product))
        self.assertFalse(_is_panel_category(self.battery_product))

    def test_product_in_unrelated_category_is_neither(self):
        other_cat = self.env['product.category'].create({'name': 'Other'})
        other_product = self.env['product.product'].create({
            'name': 'Unrelated Widget',
            'categ_id': other_cat.id,
        })
        self.assertFalse(_is_panel_category(other_product))
        self.assertFalse(_is_battery_category(other_product))

    def test_simulation_computes_panel_data_from_sale_order(self):
        """pv.simulation auto-detects panel count and power from the SO."""
        sim = self._make_simulation()
        # 10 panels × 400 Wc = 4000 Wc total
        self.assertEqual(sim.number_of_panels, 10)
        self.assertEqual(sim.panel_unit_power_wc, 400.0)
        self.assertAlmostEqual(sim.total_pv_power_wc, 4000.0, places=2)

    def test_simulation_computes_battery_data_from_sale_order(self):
        """pv.simulation auto-detects battery capacity and efficiency."""
        sim = self._make_simulation()
        self.assertEqual(sim.battery_capacity_kwh, 10.0)
        self.assertEqual(sim.battery_efficiency, 100.0)

    def test_default_battery_efficiency_is_100(self):
        """New battery products default to 100% efficiency."""
        battery = self.env['product.template'].create({
            'name': 'Fresh Battery',
            'categ_id': self.cat_batteries.id,
            'battery_capacity_kwh': 5.0,
        })
        self.assertEqual(battery.battery_efficiency_percent, 100.0)
