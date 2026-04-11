# -*- coding: utf-8 -*-

from odoo import models, fields, api

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
        string='Puissance unitaire panneau (Wc)',
        help='Puissance de sortie par panneau en Wc (Watts-crête)'
    )
    battery_capacity_kwh = fields.Float(
        string='Capacité batterie (kWh)',
        help='Capacité totale de la batterie en kWh'
    )
    battery_efficiency_percent = fields.Float(
        string='Rendement batterie (%)',
        default=100.0,
        help='Rendement aller-retour de la batterie en pourcentage (par défaut : 100 %)'
    )
    is_panel_category = fields.Boolean(
        compute='_compute_is_panel_category',
        store=False,
    )
    is_battery_category = fields.Boolean(
        compute='_compute_is_battery_category',
        store=False,
    )

    @api.depends('categ_id', 'categ_id.complete_name')
    def _compute_is_panel_category(self):
        for rec in self:
            rec.is_panel_category = _is_panel_category(rec)

    @api.depends('categ_id', 'categ_id.complete_name')
    def _compute_is_battery_category(self):
        for rec in self:
            rec.is_battery_category = _is_battery_category(rec)
