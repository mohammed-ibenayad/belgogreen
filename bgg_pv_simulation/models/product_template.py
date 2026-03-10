# -*- coding: utf-8 -*-

from odoo import models, fields, api

PANEL_CATEGORY = 'All / Saleable / Panneaux'
BATTERY_CATEGORY = 'All / Saleable / Batteries'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_solar_panel = fields.Boolean(
        string='Is Solar Panel',
        compute='_compute_is_solar_panel',
        store=True,
        help='Automatically set when the product belongs to the "Panneaux" category (All / Saleable / Panneaux)'
    )
    panel_unit_power_wc = fields.Float(
        string='Panel Unit Power (Wc)',
        help='Power output per panel in Wc (Watts-crête)'
    )

    is_battery = fields.Boolean(
        string='Is Battery',
        compute='_compute_is_battery',
        store=True,
        help='Automatically set when the product belongs to the "Batteries" category (All / Saleable / Batteries)'
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

    @api.depends('categ_id', 'categ_id.parent_id')
    def _compute_is_solar_panel(self):
        for record in self:
            complete_name = record.categ_id.complete_name or ''
            record.is_solar_panel = (
                complete_name == PANEL_CATEGORY
                or complete_name.startswith(PANEL_CATEGORY + ' / ')
            )

    @api.depends('categ_id', 'categ_id.parent_id')
    def _compute_is_battery(self):
        for record in self:
            complete_name = record.categ_id.complete_name or ''
            record.is_battery = (
                complete_name == BATTERY_CATEGORY
                or complete_name.startswith(BATTERY_CATEGORY + ' / ')
            )
