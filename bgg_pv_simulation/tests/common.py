# -*- coding: utf-8 -*-
"""Shared fixtures for pv.simulation tests.

Sets up the minimum Odoo world needed to create a simulation end-to-end
without touching Google Solar API or PVGIS:

* product categories matching the 'All / Saleable / Panneaux' and
  'All / Saleable / Batteries' paths that the module uses to detect
  panels and batteries on a sale order,
* a panel product with a unit wattage,
* a battery product with capacity and efficiency,
* a partner with a proper address,
* a sale order linking the two products,
* a tariff profile used to seed the simulation's financial overrides.

Every concrete test class inherits :class:`PvSimulationTestBase` and
uses these fixtures to build simulations directly, bypassing the
regeneration flow (which would try to call external APIs).
"""

from odoo.tests.common import TransactionCase


class PvSimulationTestBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        ProductCategory = cls.env['product.category']

        def _ensure_category(name, parent=None):
            domain = [('name', '=', name)]
            domain.append(('parent_id', '=', parent.id if parent else False))
            found = ProductCategory.search(domain, limit=1)
            if found:
                return found
            return ProductCategory.create({
                'name': name,
                'parent_id': parent.id if parent else False,
            })

        cls.cat_all = _ensure_category('All')
        cls.cat_saleable = _ensure_category('Saleable', cls.cat_all)
        cls.cat_panels = _ensure_category('Panneaux', cls.cat_saleable)
        cls.cat_batteries = _ensure_category('Batteries', cls.cat_saleable)

        # Panel product: 400 Wc each.
        cls.panel_product = cls.env['product.product'].create({
            'name': 'Test Panel 400Wc',
            'type': 'consu',
            'categ_id': cls.cat_panels.id,
            'list_price': 300.0,
            'panel_unit_power_wc': 400.0,
        })

        # Battery product: 10 kWh capacity @ 100% efficiency.
        cls.battery_product = cls.env['product.product'].create({
            'name': 'Test Battery 10kWh',
            'type': 'consu',
            'categ_id': cls.cat_batteries.id,
            'list_price': 5000.0,
            'battery_capacity_kwh': 10.0,
            'battery_efficiency_percent': 100.0,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test PV Customer',
            'street': '10 Rue du Soleil',
            'zip': '1000',
            'city': 'Brussels',
            'country_id': cls.env.ref('base.be').id,
        })

        cls.tariff_profile = cls.env['pv.tariff.profile'].create({
            'name': 'Test Tariff',
            'purchase_price_kwh': 0.30,
            'feed_in_tariff_kwh': 0.05,
            'battery_cost_kwh': 0.02,
        })

        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': cls.panel_product.id,
                    'product_uom_qty': 10,  # 10 × 400 Wc = 4000 Wc
                }),
                (0, 0, {
                    'product_id': cls.battery_product.id,
                    'product_uom_qty': 1,   # 10 kWh
                }),
            ],
        })

    def _make_simulation(self, **overrides):
        """Create a pv.simulation bound to the default sale order.

        ``overrides`` lets the caller pre-set any field on the simulation
        (e.g. tariff overrides, section titles) to customise a scenario.
        """
        vals = {
            'sale_order_id': self.sale_order.id,
            'tariff_profile_id': self.tariff_profile.id,
            'purchase_price_kwh': self.tariff_profile.purchase_price_kwh,
            'feed_in_tariff_kwh': self.tariff_profile.feed_in_tariff_kwh,
            'battery_cost_kwh': self.tariff_profile.battery_cost_kwh,
        }
        vals.update(overrides)
        return self.env['pv.simulation'].create(vals)

    def _make_monthly_result(self, simulation, month, prod_day, conso_day, conso_night):
        """Create a single pv.monthly.result pre-filled with daily values.

        ``prod_day``, ``conso_day`` and ``conso_night`` are per-day kWh
        values; the monthly totals are derived by the model from
        ``days_in_month``.
        """
        return self.env['pv.monthly.result'].create({
            'simulation_id': simulation.id,
            'month': str(month),
            'daily_production_kwh': prod_day,
            'daily_day_consumption_kwh': conso_day,
            'daily_night_consumption_kwh': conso_night,
        })
