# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PvConsumptionProfile(models.Model):
    _name = 'pv.consumption.profile'
    _description = 'PV Consumption Profile'
    _order = 'name'

    name = fields.Char(
        string='Profile Name',
        required=True,
        translate=True
    )
    annual_consumption_kwh = fields.Float(
        string='Annual Consumption (kWh)',
        required=True,
        help='Total yearly electricity consumption in kWh'
    )
    daily_day_consumption_kwh = fields.Float(
        string='Daily Day Consumption (kWh)',
        required=True,
        help='Daily daytime electricity usage in kWh'
    )
    daily_night_consumption_kwh = fields.Float(
        string='Daily Night Consumption (kWh)',
        required=True,
        help='Daily nighttime electricity usage in kWh'
    )
    monthly_consumption_kwh = fields.Float(
        string='Monthly Consumption (kWh)',
        compute='_compute_monthly_consumption_kwh',
        store=True,
        help='Computed: Annual consumption / 12'
    )
    daily_total_consumption_kwh = fields.Float(
        string='Daily Total Consumption (kWh)',
        compute='_compute_daily_total_consumption_kwh',
        store=True,
        help='Computed: Day consumption + Night consumption'
    )

    @api.depends('annual_consumption_kwh')
    def _compute_monthly_consumption_kwh(self):
        for record in self:
            record.monthly_consumption_kwh = record.annual_consumption_kwh / 12.0

    @api.depends('daily_day_consumption_kwh', 'daily_night_consumption_kwh')
    def _compute_daily_total_consumption_kwh(self):
        for record in self:
            record.daily_total_consumption_kwh = (
                record.daily_day_consumption_kwh +
                record.daily_night_consumption_kwh
            )

    @api.constrains('annual_consumption_kwh', 'daily_day_consumption_kwh', 'daily_night_consumption_kwh')
    def _check_consumption_values(self):
        for record in self:
            if record.annual_consumption_kwh < 0:
                raise ValidationError(_('Annual consumption cannot be negative.'))
            if record.daily_day_consumption_kwh < 0:
                raise ValidationError(_('Daily day consumption cannot be negative.'))
            if record.daily_night_consumption_kwh < 0:
                raise ValidationError(_('Daily night consumption cannot be negative.'))
