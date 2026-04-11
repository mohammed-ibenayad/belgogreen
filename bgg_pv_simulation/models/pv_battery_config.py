# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PvBatteryConfig(models.Model):
    _name = 'pv.battery.config'
    _description = 'Configuration batterie PV'
    _order = 'name'

    name = fields.Char(
        string='Nom de la configuration',
        required=True,
        translate=True
    )
    capacity_kwh = fields.Float(
        string='Capacité nominale (kWh)',
        required=True,
        help='Capacité nominale de la batterie en kWh'
    )
    usable_ratio = fields.Float(
        string='Ratio utilisable',
        required=True,
        default=0.95,
        help='Pourcentage utilisable de la capacité (0 à 1), typiquement 0,90 à 0,95'
    )
    max_daily_charge_kwh = fields.Float(
        string='Charge quotidienne max (kWh)',
        required=True,
        help='Limite de charge quotidienne maximale en kWh'
    )
    efficiency = fields.Float(
        string='Rendement',
        required=True,
        default=0.95,
        help='Rendement aller-retour (0 à 1)'
    )
    cost_per_kwh = fields.Monetary(
        string="Coût d'usure (€/kWh)",
        required=True,
        default=0.02,
        currency_field='currency_id',
        help="Coût d'usure par kWh cyclé dans la batterie"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    @api.constrains('usable_ratio', 'efficiency')
    def _check_ratios(self):
        for record in self:
            if not (0 < record.usable_ratio <= 1):
                raise ValidationError(_('Le ratio utilisable doit être compris entre 0 et 1.'))
            if not (0 < record.efficiency <= 1):
                raise ValidationError(_('Le rendement doit être compris entre 0 et 1.'))

    @api.constrains('capacity_kwh', 'max_daily_charge_kwh')
    def _check_capacity(self):
        for record in self:
            if record.capacity_kwh <= 0:
                raise ValidationError(_('La capacité doit être positive.'))
            if record.max_daily_charge_kwh <= 0:
                raise ValidationError(_('La charge quotidienne maximale doit être positive.'))

    @api.constrains('cost_per_kwh')
    def _check_cost(self):
        for record in self:
            if record.cost_per_kwh < 0:
                raise ValidationError(_("Le coût d'usure ne peut pas être négatif."))
