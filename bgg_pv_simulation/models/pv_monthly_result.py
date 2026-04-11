# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PvMonthlyResult(models.Model):
    _name = 'pv.monthly.result'
    _description = 'Résultat mensuel PV'
    _order = 'simulation_id, month_sequence'

    simulation_id = fields.Many2one(
        'pv.simulation',
        string='Simulation',
        required=True,
        ondelete='cascade'
    )
    month = fields.Selection(
        selection=[
            ('1', 'Janvier'),
            ('2', 'Février'),
            ('3', 'Mars'),
            ('4', 'Avril'),
            ('5', 'Mai'),
            ('6', 'Juin'),
            ('7', 'Juillet'),
            ('8', 'Août'),
            ('9', 'Septembre'),
            ('10', 'Octobre'),
            ('11', 'Novembre'),
            ('12', 'Décembre'),
        ],
        string='Mois',
        required=True
    )
    month_sequence = fields.Integer(
        string='Ordre du mois',
        compute='_compute_month_sequence',
        store=True,
        help='Numéro de mois utilisé pour le tri'
    )
    days_in_month = fields.Integer(
        string='Jours dans le mois',
        compute='_compute_days_in_month',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        related='simulation_id.currency_id',
        store=True
    )

    # Monthly Energy Totals
    monthly_production_kwh = fields.Float(
        string='Production mensuelle (kWh)',
        help='Production totale pour le mois'
    )
    monthly_consumption_kwh = fields.Float(
        string='Consommation mensuelle (kWh)',
        help='Consommation totale pour le mois'
    )
    monthly_day_consumption_kwh = fields.Float(
        string='Consommation jour mensuelle (kWh)',
        help='Consommation de jour pour le mois'
    )
    monthly_night_consumption_kwh = fields.Float(
        string='Consommation nuit mensuelle (kWh)',
        help='Consommation de nuit pour le mois'
    )
    monthly_battery_charge_kwh = fields.Float(
        string='Charge batterie mensuelle (kWh)',
        help='Énergie stockée dans la batterie pour le mois'
    )
    monthly_energy_sold_kwh = fields.Float(
        string='Énergie vendue mensuelle (kWh)',
        help='Énergie revendue au réseau pour le mois'
    )
    monthly_energy_bought_kwh = fields.Float(
        string='Énergie achetée mensuelle (kWh)',
        help='Énergie achetée au réseau pour le mois'
    )
    monthly_autoconsumption_kwh = fields.Float(
        string='Autoconsommation mensuelle (kWh)',
        help='Autoconsommation totale pour le mois'
    )

    # Daily Averages
    daily_production_kwh = fields.Float(
        string='Production quotidienne (kWh)',
        help='Production quotidienne moyenne'
    )
    daily_day_consumption_kwh = fields.Float(
        string='Consommation jour quotidienne (kWh)',
        help='Consommation de jour quotidienne'
    )
    daily_night_consumption_kwh = fields.Float(
        string='Consommation nuit quotidienne (kWh)',
        help='Consommation de nuit quotidienne'
    )
    daily_day_autoconsumption_kwh = fields.Float(
        string='Autoconsommation directe quotidienne (kWh)',
        help='Autoconsommation directe quotidienne (production consommée directement en journée)'
    )
    daily_surplus_pv_kwh = fields.Float(
        string='Surplus PV quotidien (kWh)',
        help='Surplus solaire quotidien après consommation de jour (Production − Conso jour, si > 0)'
    )
    daily_battery_charge_kwh = fields.Float(
        string='Charge batterie quotidienne (kWh)',
        help='Énergie stockée dans la batterie par jour'
    )
    daily_energy_sold_kwh = fields.Float(
        string='Énergie vendue quotidienne (kWh)',
        help='Énergie revendue au réseau par jour'
    )
    daily_energy_bought_kwh = fields.Float(
        string='Énergie achetée quotidienne (kWh)',
        help='Énergie achetée au réseau par jour'
    )
    battery_charge_level = fields.Integer(
        string='Niveau batterie',
        compute='_compute_battery_charge_level',
        store=False,
        help='Niveau de charge de la batterie (0-7), utilisé pour l\'icône'
    )

    # Monthly Financial Totals
    panel_savings = fields.Monetary(
        string='Économies panneaux',
        currency_field='currency_id',
        help='Économies réalisées grâce aux panneaux (autoconsommation de jour)'
    )
    battery_savings = fields.Monetary(
        string='Économies batterie',
        currency_field='currency_id',
        help='Économies réalisées grâce à la batterie (consommation de nuit)'
    )
    sale_revenue = fields.Monetary(
        string='Revenus de revente',
        currency_field='currency_id',
        help='Revenus générés par la revente du surplus au réseau'
    )
    purchase_cost = fields.Monetary(
        string="Coût d'achat réseau",
        currency_field='currency_id',
        help="Coût de l'énergie achetée au réseau"
    )
    net_balance = fields.Monetary(
        string='Bilan net',
        currency_field='currency_id',
        help="Bilan net = coût d'achat − revenus de revente"
    )

    @api.onchange('monthly_consumption_kwh')
    def _onchange_monthly_consumption(self):
        """Auto-derive daily day/night consumption from monthly total using the ratio."""
        for record in self:
            monthly = record.monthly_consumption_kwh or 0.0
            days = record.days_in_month or 30
            ratio = record.simulation_id.day_consumption_ratio if record.simulation_id else 0.6
            if ratio <= 0 or ratio >= 1:
                ratio = 0.6
            daily_total = monthly / days if days else 0.0
            record.daily_day_consumption_kwh = round(daily_total * ratio, 2)
            record.daily_night_consumption_kwh = round(daily_total * (1 - ratio), 2)
            record.monthly_day_consumption_kwh = round(monthly * ratio, 2)
            record.monthly_night_consumption_kwh = round(monthly * (1 - ratio), 2)

    @api.depends('month')
    def _compute_month_sequence(self):
        """Convert month string to integer for proper sorting"""
        for record in self:
            if record.month:
                record.month_sequence = int(record.month)
            else:
                record.month_sequence = 0

    @api.depends('month')
    def _compute_days_in_month(self):
        days = {
            1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
            7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
        }
        for record in self:
            if record.month:
                month_int = int(record.month)
                record.days_in_month = days.get(month_int, 30)
            else:
                record.days_in_month = 30

    @api.depends('daily_battery_charge_kwh', 'simulation_id.battery_capacity_kwh',
                 'simulation_id.battery_efficiency')
    def _compute_battery_charge_level(self):
        """Compute battery icon level (0-7) from charge ratio.

        0 = empty (no battery or 0 charge)
        1-7 = proportional to daily_charge / (capacity * efficiency)
        """
        for record in self:
            cap = record.simulation_id.battery_capacity_kwh or 0.0
            eff = (record.simulation_id.battery_efficiency or 0.0) / 100.0
            max_charge = cap * eff
            charge = record.daily_battery_charge_kwh or 0.0

            if max_charge <= 0 or charge <= 0:
                record.battery_charge_level = 0
            else:
                ratio = min(charge / max_charge, 1.0)
                # Map ratio to 1-7 (ceil so any charge > 0 shows at least level 1)
                record.battery_charge_level = max(1, min(7, int(ratio * 7 + 0.5)))
