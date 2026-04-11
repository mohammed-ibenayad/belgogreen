# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PvTariffProfile(models.Model):
    _name = 'pv.tariff.profile'
    _description = 'Profil tarifaire PV'
    _order = 'name'

    name = fields.Char(
        string='Nom du profil',
        required=True,
        translate=True
    )
    purchase_price_kwh = fields.Monetary(
        string="Prix d'achat (€/kWh)",
        required=True,
        currency_field='currency_id',
        help="Prix d'achat de l'électricité au réseau par kWh"
    )
    feed_in_tariff_kwh = fields.Monetary(
        string='Tarif de revente (€/kWh)',
        required=True,
        currency_field='currency_id',
        help='Tarif de revente du surplus au réseau par kWh'
    )
    battery_cost_kwh = fields.Monetary(
        string='Coût batterie (€/kWh)',
        currency_field='currency_id',
        default=0.02,
        help="Coût d'usure par kWh cyclé dans la batterie (P_batt)"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    @api.constrains('purchase_price_kwh', 'feed_in_tariff_kwh')
    def _check_prices(self):
        for record in self:
            if record.purchase_price_kwh <= 0:
                raise ValidationError(_("Le prix d'achat doit être positif."))
            if record.feed_in_tariff_kwh < 0:
                raise ValidationError(_('Le tarif de revente ne peut pas être négatif.'))
