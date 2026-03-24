# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PvProductionProfile(models.Model):
    _name = 'pv.production.profile'
    _description = 'PV Production Profile'
    _order = 'name'

    name = fields.Char(
        string='Profile Name',
        required=True,
        translate=True
    )
    january_pct = fields.Float(
        string='January (%)',
        required=True,
        help='Percentage of annual production in January'
    )
    february_pct = fields.Float(
        string='February (%)',
        required=True,
        help='Percentage of annual production in February'
    )
    march_pct = fields.Float(
        string='March (%)',
        required=True,
        help='Percentage of annual production in March'
    )
    april_pct = fields.Float(
        string='April (%)',
        required=True,
        help='Percentage of annual production in April'
    )
    may_pct = fields.Float(
        string='May (%)',
        required=True,
        help='Percentage of annual production in May'
    )
    june_pct = fields.Float(
        string='June (%)',
        required=True,
        help='Percentage of annual production in June'
    )
    july_pct = fields.Float(
        string='July (%)',
        required=True,
        help='Percentage of annual production in July'
    )
    august_pct = fields.Float(
        string='August (%)',
        required=True,
        help='Percentage of annual production in August'
    )
    september_pct = fields.Float(
        string='September (%)',
        required=True,
        help='Percentage of annual production in September'
    )
    october_pct = fields.Float(
        string='October (%)',
        required=True,
        help='Percentage of annual production in October'
    )
    november_pct = fields.Float(
        string='November (%)',
        required=True,
        help='Percentage of annual production in November'
    )
    december_pct = fields.Float(
        string='December (%)',
        required=True,
        help='Percentage of annual production in December'
    )
    total_pct = fields.Float(
        string='Total (%)',
        compute='_compute_total_pct',
        store=True,
        help='Sum of all monthly percentages (must equal 100%)'
    )

    @api.depends('january_pct', 'february_pct', 'march_pct', 'april_pct',
                 'may_pct', 'june_pct', 'july_pct', 'august_pct',
                 'september_pct', 'october_pct', 'november_pct', 'december_pct')
    def _compute_total_pct(self):
        for record in self:
            record.total_pct = sum([
                record.january_pct, record.february_pct, record.march_pct,
                record.april_pct, record.may_pct, record.june_pct,
                record.july_pct, record.august_pct, record.september_pct,
                record.october_pct, record.november_pct, record.december_pct
            ])

    @api.constrains('january_pct', 'february_pct', 'march_pct', 'april_pct',
                    'may_pct', 'june_pct', 'july_pct', 'august_pct',
                    'september_pct', 'october_pct', 'november_pct', 'december_pct')
    def _check_total_percentage(self):
        for record in self:
            total = sum([
                record.january_pct, record.february_pct, record.march_pct,
                record.april_pct, record.may_pct, record.june_pct,
                record.july_pct, record.august_pct, record.september_pct,
                record.october_pct, record.november_pct, record.december_pct
            ])
            if abs(total - 100.0) > 0.01:
                raise ValidationError(
                    _('Monthly percentages must sum to 100%%. Current total: %.2f%%') % total
                )

    def get_month_pct(self, month_num):
        """Helper method to get percentage for a given month number (1-12)"""
        self.ensure_one()
        month_fields = [
            'january_pct', 'february_pct', 'march_pct', 'april_pct',
            'may_pct', 'june_pct', 'july_pct', 'august_pct',
            'september_pct', 'october_pct', 'november_pct', 'december_pct'
        ]
        if 1 <= month_num <= 12:
            return getattr(self, month_fields[month_num - 1])
        return 0.0
