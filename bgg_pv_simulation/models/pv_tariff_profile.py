# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PvTariffProfile(models.Model):
    _name = 'pv.tariff.profile'
    _description = 'PV Tariff Profile'
    _order = 'name'

    name = fields.Char(
        string='Tariff Name',
        required=True,
        translate=True
    )
    purchase_price_kwh = fields.Monetary(
        string='Purchase Price (€/kWh)',
        required=True,
        currency_field='currency_id',
        help='Grid purchase price per kWh'
    )
    feed_in_tariff_kwh = fields.Monetary(
        string='Feed-in Tariff (€/kWh)',
        required=True,
        currency_field='currency_id',
        help='Grid sale price per kWh'
    )
    battery_cost_kwh = fields.Monetary(
        string='Battery Cost (€/kWh)',
        currency_field='currency_id',
        default=0.02,
        help='Cost per kWh cycled through battery (P_batt)'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    @api.constrains('purchase_price_kwh', 'feed_in_tariff_kwh')
    def _check_prices(self):
        for record in self:
            if record.purchase_price_kwh <= 0:
                raise ValidationError(_('Purchase price must be positive.'))
            if record.feed_in_tariff_kwh < 0:
                raise ValidationError(_('Feed-in tariff cannot be negative.'))
