# -*- coding: utf-8 -*-

from odoo import models, fields

PANEL_CATEGORY = 'All / Saleable / Panneaux'
BATTERY_CATEGORY = 'All / Saleable / Batteries'


def _is_panel_category(product):
    """Check if product belongs to the solar panel category."""
    complete_name = product.categ_id.complete_name or ''
    return (
        complete_name == PANEL_CATEGORY
        or complete_name.startswith(PANEL_CATEGORY + ' / ')
    )


def _is_battery_category(product):
    """Check if product belongs to the battery category."""
    complete_name = product.categ_id.complete_name or ''
    return (
        complete_name == BATTERY_CATEGORY
        or complete_name.startswith(BATTERY_CATEGORY + ' / ')
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    panel_unit_power_wc = fields.Float(
        string='Panel Unit Power (Wc)',
        help='Power output per panel in Wc (Watts-crête)'
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
