# -*- coding: utf-8 -*-
"""Tests for :class:`pv.production.profile` validation."""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestProductionProfile(TransactionCase):

    def _make_profile_vals(self, **overrides):
        """Return a valid 12-month profile (summing to 100%)."""
        vals = {
            'name': 'Test Profile',
            'january_pct': 5.0,
            'february_pct': 5.0,
            'march_pct': 10.0,
            'april_pct': 10.0,
            'may_pct': 10.0,
            'june_pct': 10.0,
            'july_pct': 10.0,
            'august_pct': 10.0,
            'september_pct': 10.0,
            'october_pct': 10.0,
            'november_pct': 5.0,
            'december_pct': 5.0,
        }
        vals.update(overrides)
        return vals

    def test_valid_profile_sums_to_100(self):
        profile = self.env['pv.production.profile'].create(self._make_profile_vals())
        self.assertAlmostEqual(profile.total_pct, 100.0, places=2)

    def test_get_month_pct_returns_correct_value(self):
        profile = self.env['pv.production.profile'].create(self._make_profile_vals())
        self.assertEqual(profile.get_month_pct(1), 5.0)
        self.assertEqual(profile.get_month_pct(3), 10.0)
        self.assertEqual(profile.get_month_pct(12), 5.0)

    def test_get_month_pct_out_of_range(self):
        profile = self.env['pv.production.profile'].create(self._make_profile_vals())
        self.assertEqual(profile.get_month_pct(0), 0.0)
        self.assertEqual(profile.get_month_pct(13), 0.0)

    def test_profile_rejected_when_total_is_not_100(self):
        vals = self._make_profile_vals(january_pct=20.0)  # total = 115
        with self.assertRaises(ValidationError):
            self.env['pv.production.profile'].create(vals)
