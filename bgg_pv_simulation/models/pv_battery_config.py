# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PvBatteryConfig(models.Model):
    _name = 'pv.battery.config'
    _description = 'PV Battery Configuration'
    _order = 'name'

    name = fields.Char(
        string='Configuration Name',
        required=True,
        translate=True
    )
    capacity_kwh = fields.Float(
        string='Nominal Capacity (kWh)',
        required=True,
        help='Battery nominal capacity in kWh'
    )
    usable_ratio = fields.Float(
        string='Usable Ratio',
        required=True,
        default=0.95,
        help='Usable percentage of capacity (0-1), typically 0.90-0.95'
    )
    max_daily_charge_kwh = fields.Float(
        string='Max Daily Charge (kWh)',
        required=True,
        help='Maximum daily charge limit in kWh'
    )
    efficiency = fields.Float(
        string='Efficiency',
        required=True,
        default=0.95,
        help='Round-trip efficiency (0-1)'
    )
    cost_per_kwh = fields.Monetary(
        string='Degradation Cost (€/kWh)',
        required=True,
        default=0.02,
        currency_field='currency_id',
        help='Degradation cost per kWh cycled'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    @api.constrains('usable_ratio', 'efficiency')
    def _check_ratios(self):
        for record in self:
            if not (0 < record.usable_ratio <= 1):
                raise ValidationError(_('Usable ratio must be between 0 and 1.'))
            if not (0 < record.efficiency <= 1):
                raise ValidationError(_('Efficiency must be between 0 and 1.'))

    @api.constrains('capacity_kwh', 'max_daily_charge_kwh')
    def _check_capacity(self):
        for record in self:
            if record.capacity_kwh <= 0:
                raise ValidationError(_('Capacity must be positive.'))
            if record.max_daily_charge_kwh <= 0:
                raise ValidationError(_('Max daily charge must be positive.'))

    @api.constrains('cost_per_kwh')
    def _check_cost(self):
        for record in self:
            if record.cost_per_kwh < 0:
                raise ValidationError(_('Degradation cost cannot be negative.'))
