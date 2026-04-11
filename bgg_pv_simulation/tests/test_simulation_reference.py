# -*- coding: utf-8 -*-
"""Tests for the ``SIM-<SO>-vNN`` reference and version bump behaviour."""

from odoo.tests import tagged

from .common import PvSimulationTestBase


@tagged('post_install', '-at_install')
class TestSimulationReference(PvSimulationTestBase):

    def test_format_simulation_name_pads_version(self):
        Simulation = self.env['pv.simulation']
        self.assertEqual(
            Simulation._format_simulation_name('S00010', 1),
            'SIM-S00010-v01',
        )
        self.assertEqual(
            Simulation._format_simulation_name('S00010', 12),
            'SIM-S00010-v12',
        )

    def test_new_simulation_starts_at_v01(self):
        sim = self._make_simulation()
        self.assertEqual(sim.version, 1)
        self.assertEqual(sim.name, f'SIM-{self.sale_order.name}-v01')

    def test_bump_version_increments_name_and_field(self):
        sim = self._make_simulation()
        sim._bump_version()
        self.assertEqual(sim.version, 2)
        self.assertEqual(sim.name, f'SIM-{self.sale_order.name}-v02')

        sim._bump_version()
        self.assertEqual(sim.version, 3)
        self.assertEqual(sim.name, f'SIM-{self.sale_order.name}-v03')

    def test_version_field_is_not_copied(self):
        """A duplicated simulation must NOT carry the previous version."""
        sim = self._make_simulation()
        sim._bump_version()  # now v02
        copy = sim.copy({'sale_order_id': self.sale_order.id})
        self.assertEqual(copy.version, 1)

    def test_next_reference_without_sale_order_uses_sequence(self):
        """Callers without an SO still get a unique SIM- reference."""
        Simulation = self.env['pv.simulation']
        ref = Simulation._next_simulation_reference(sale_order=None)
        self.assertTrue(ref.startswith('SIM-'))
        self.assertNotIn('-v', ref)  # legacy sequence, not SO-based
