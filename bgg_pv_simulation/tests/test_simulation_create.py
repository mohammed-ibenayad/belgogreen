# -*- coding: utf-8 -*-
"""Tests for the :meth:`pv.simulation.create` override."""

from odoo.tests import tagged

from .common import PvSimulationTestBase


@tagged('post_install', '-at_install')
class TestSimulationCreate(PvSimulationTestBase):

    def test_create_auto_applies_first_tariff_profile(self):
        """When no tariff is supplied, the first profile is used."""
        # Remove any other tariff profiles so our fixture wins deterministically.
        other = self.env['pv.tariff.profile'].search([
            ('id', '!=', self.tariff_profile.id),
        ])
        other.unlink()

        sim = self.env['pv.simulation'].create({
            'sale_order_id': self.sale_order.id,
        })
        self.assertEqual(sim.tariff_profile_id, self.tariff_profile)
        self.assertAlmostEqual(sim.purchase_price_kwh, 0.30, places=2)
        self.assertAlmostEqual(sim.feed_in_tariff_kwh, 0.05, places=2)
        self.assertAlmostEqual(sim.battery_cost_kwh, 0.02, places=2)

    def test_create_honours_explicit_tariff_profile(self):
        custom = self.env['pv.tariff.profile'].create({
            'name': 'Custom',
            'purchase_price_kwh': 0.40,
            'feed_in_tariff_kwh': 0.10,
            'battery_cost_kwh': 0.03,
        })
        sim = self.env['pv.simulation'].create({
            'sale_order_id': self.sale_order.id,
            'tariff_profile_id': custom.id,
        })
        self.assertEqual(sim.tariff_profile_id, custom)
        self.assertAlmostEqual(sim.purchase_price_kwh, 0.40, places=2)
        self.assertAlmostEqual(sim.feed_in_tariff_kwh, 0.10, places=2)
        self.assertAlmostEqual(sim.battery_cost_kwh, 0.03, places=2)

    def test_create_resolves_name_from_sale_order(self):
        sim = self.env['pv.simulation'].create({
            'sale_order_id': self.sale_order.id,
        })
        self.assertEqual(sim.name, f'SIM-{self.sale_order.name}-v01')
        self.assertEqual(sim.version, 1)

    def test_multiple_simulations_both_start_at_v01(self):
        """Creating two simulations for the same SO: both start at v01.

        The version only tracks regenerations of a given simulation; it
        does NOT count sibling simulations for the same sale order.
        """
        sim1 = self.env['pv.simulation'].create({
            'sale_order_id': self.sale_order.id,
        })
        sim2 = self.env['pv.simulation'].create({
            'sale_order_id': self.sale_order.id,
        })
        self.assertEqual(sim1.version, 1)
        self.assertEqual(sim2.version, 1)
        self.assertEqual(sim1.name, f'SIM-{self.sale_order.name}-v01')
        self.assertEqual(sim2.name, f'SIM-{self.sale_order.name}-v01')

    def test_create_preserves_explicit_overrides(self):
        """Explicitly-provided prices win over tariff-profile defaults."""
        sim = self.env['pv.simulation'].create({
            'sale_order_id': self.sale_order.id,
            'tariff_profile_id': self.tariff_profile.id,
            'purchase_price_kwh': 0.99,
        })
        self.assertAlmostEqual(sim.purchase_price_kwh, 0.99, places=2)
        # The ones not overridden fall back to the profile.
        self.assertAlmostEqual(sim.feed_in_tariff_kwh, 0.05, places=2)
