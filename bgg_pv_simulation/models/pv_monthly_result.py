# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PvMonthlyResult(models.Model):
    _name = 'pv.monthly.result'
    _description = 'PV Monthly Result'
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
        string='Month Sequence',
        compute='_compute_month_sequence',
        store=True,
        help='Numeric month value for proper sorting'
    )
    days_in_month = fields.Integer(
        string='Days in Month',
        compute='_compute_days_in_month',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='simulation_id.currency_id',
        store=True
    )

    # Monthly Energy Totals
    monthly_production_kwh = fields.Float(
        string='Monthly Production (kWh)',
        help='Total production for the month'
    )
    monthly_consumption_kwh = fields.Float(
        string='Monthly Consumption (kWh)',
        help='Total consumption for the month'
    )
    monthly_day_consumption_kwh = fields.Float(
        string='Monthly Day Consumption (kWh)',
        help='Day consumption for the month'
    )
    monthly_night_consumption_kwh = fields.Float(
        string='Monthly Night Consumption (kWh)',
        help='Night consumption for the month'
    )
    monthly_battery_charge_kwh = fields.Float(
        string='Monthly Battery Charge (kWh)',
        help='Energy stored for the month'
    )
    monthly_energy_sold_kwh = fields.Float(
        string='Monthly Energy Sold (kWh)',
        help='Energy sold for the month'
    )
    monthly_energy_bought_kwh = fields.Float(
        string='Monthly Energy Bought (kWh)',
        help='Energy bought for the month'
    )
    monthly_autoconsumption_kwh = fields.Float(
        string='Monthly Autoconsumption (kWh)',
        help='Total self-consumed for the month'
    )

    # Daily Averages
    daily_production_kwh = fields.Float(
        string='Daily Production (kWh)',
        help='Average daily production'
    )
    daily_day_consumption_kwh = fields.Float(
        string='Daily Day Consumption (kWh)',
        help='Daily day consumption'
    )
    daily_night_consumption_kwh = fields.Float(
        string='Daily Night Consumption (kWh)',
        help='Daily night consumption'
    )
    daily_day_autoconsumption_kwh = fields.Float(
        string='Daily Direct Autoconsumption (kWh)',
        help='Daily direct self-consumption'
    )
    daily_surplus_pv_kwh = fields.Float(
        string='Daily Surplus PV (kWh)',
        help='Daily solar surplus after day consumption (Production - Conso jour, if > 0)'
    )
    daily_battery_charge_kwh = fields.Float(
        string='Daily Battery Charge (kWh)',
        help='Daily battery charge'
    )
    daily_energy_sold_kwh = fields.Float(
        string='Daily Energy Sold (kWh)',
        help='Daily energy sold'
    )
    daily_energy_bought_kwh = fields.Float(
        string='Daily Energy Bought (kWh)',
        help='Daily energy bought'
    )

    # Monthly Financial Totals
    panel_savings = fields.Monetary(
        string='Panel Savings',
        currency_field='currency_id',
        help='€ saved from panels'
    )
    battery_savings = fields.Monetary(
        string='Battery Savings',
        currency_field='currency_id',
        help='€ saved from battery'
    )
    sale_revenue = fields.Monetary(
        string='Sale Revenue',
        currency_field='currency_id',
        help='€ from grid sales'
    )
    purchase_cost = fields.Monetary(
        string='Purchase Cost',
        currency_field='currency_id',
        help='€ for grid purchases'
    )
    net_balance = fields.Monetary(
        string='Net Balance',
        currency_field='currency_id',
        help='purchase_cost - sale_revenue'
    )

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
            1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
            7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
        }
        for record in self:
            if record.month:
                month_int = int(record.month)
                record.days_in_month = days.get(month_int, 30)
            else:
                record.days_in_month = 30
