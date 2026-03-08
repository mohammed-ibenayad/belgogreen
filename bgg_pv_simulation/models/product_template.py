# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_solar_panel = fields.Boolean(
        string='Is Solar Panel',
        default=False,
        help='Check this if the product is a solar panel'
    )
    panel_unit_power_wc = fields.Float(
        string='Panel Unit Power (Wc)',
        help='Power output per panel in Wc (Watts-crête)'
    )

    is_battery = fields.Boolean(
        string='Is Battery',
        default=False,
        help='Check this if the product is a battery storage system'
    )
    battery_capacity_kwh = fields.Float(
        string='Battery Capacity (kWh)',
        help='Total battery capacity in kWh'
    )
    battery_efficiency_percent = fields.Float(
        string='Battery Efficiency (%)',
        default=90.0,
        help='Battery round-trip efficiency percentage (default: 90%)'
    )

    # For better organization, you can also use product category
    # but having a boolean flag is simpler and more explicit
