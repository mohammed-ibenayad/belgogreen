# -*- coding: utf-8 -*-
"""Tests for the cent-precise annual consumption distributor.

The distributor splits an annual consumption total across 12 months so
that:
  * every per-month value has at most 2 decimals (cent-precise),
  * the sum of per-month values equals the original annual total
    exactly (no drift like 5000 -> 5000.04).
"""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestConsumptionDistribution(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Simulation = self.env['pv.simulation']

    def test_distribute_5000_sum_matches_exactly(self):
        """5000 kWh / 12 must round-trip to exactly 5000 kWh."""
        dist = self.Simulation._distribute_annual_consumption(5000.0)
        self.assertEqual(len(dist), 12)
        self.assertAlmostEqual(sum(dist), 5000.0, places=2)
        # Each value must be cent-precise (2 decimals).
        for v in dist:
            self.assertEqual(round(v, 2), v)

    def test_distribute_5000_expected_shape(self):
        """5000 / 12 -> 8 months of 416.67 + 4 months of 416.66."""
        dist = self.Simulation._distribute_annual_consumption(5000.0)
        self.assertEqual(dist.count(416.67), 8)
        self.assertEqual(dist.count(416.66), 4)

    def test_distribute_zero_returns_zeros(self):
        dist = self.Simulation._distribute_annual_consumption(0.0)
        self.assertEqual(dist, [0.0] * 12)

    def test_distribute_none_is_safe(self):
        dist = self.Simulation._distribute_annual_consumption(None)
        self.assertEqual(dist, [0.0] * 12)

    def test_distribute_12000_is_even(self):
        """12000 / 12 = 1000 exactly, so every month must be 1000.00."""
        dist = self.Simulation._distribute_annual_consumption(12000.0)
        self.assertEqual(dist, [1000.0] * 12)
        self.assertAlmostEqual(sum(dist), 12000.0, places=2)

    def test_distribute_decimal_total_no_drift(self):
        """A non-round total must still round-trip exactly."""
        dist = self.Simulation._distribute_annual_consumption(12345.67)
        self.assertAlmostEqual(sum(dist), 12345.67, places=2)
        for v in dist:
            self.assertEqual(round(v, 2), v)

    def test_distribute_custom_count(self):
        """The helper should also work for arbitrary counts."""
        dist = self.Simulation._distribute_annual_consumption(100.0, count=4)
        self.assertEqual(len(dist), 4)
        self.assertAlmostEqual(sum(dist), 100.0, places=2)

    def test_distribute_negative_count_is_safe(self):
        dist = self.Simulation._distribute_annual_consumption(100.0, count=-1)
        self.assertEqual(dist, [])
