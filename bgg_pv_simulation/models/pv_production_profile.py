# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PvProductionProfile(models.Model):
    _name = 'pv.production.profile'
    _description = 'Profil de production PV'
    _order = 'name'

    name = fields.Char(
        string='Nom du profil',
        required=True,
        translate=True
    )
    january_pct = fields.Float(
        string='Janvier (%)',
        required=True,
        help='Pourcentage de la production annuelle en janvier'
    )
    february_pct = fields.Float(
        string='Février (%)',
        required=True,
        help='Pourcentage de la production annuelle en février'
    )
    march_pct = fields.Float(
        string='Mars (%)',
        required=True,
        help='Pourcentage de la production annuelle en mars'
    )
    april_pct = fields.Float(
        string='Avril (%)',
        required=True,
        help='Pourcentage de la production annuelle en avril'
    )
    may_pct = fields.Float(
        string='Mai (%)',
        required=True,
        help='Pourcentage de la production annuelle en mai'
    )
    june_pct = fields.Float(
        string='Juin (%)',
        required=True,
        help='Pourcentage de la production annuelle en juin'
    )
    july_pct = fields.Float(
        string='Juillet (%)',
        required=True,
        help='Pourcentage de la production annuelle en juillet'
    )
    august_pct = fields.Float(
        string='Août (%)',
        required=True,
        help='Pourcentage de la production annuelle en août'
    )
    september_pct = fields.Float(
        string='Septembre (%)',
        required=True,
        help='Pourcentage de la production annuelle en septembre'
    )
    october_pct = fields.Float(
        string='Octobre (%)',
        required=True,
        help='Pourcentage de la production annuelle en octobre'
    )
    november_pct = fields.Float(
        string='Novembre (%)',
        required=True,
        help='Pourcentage de la production annuelle en novembre'
    )
    december_pct = fields.Float(
        string='Décembre (%)',
        required=True,
        help='Pourcentage de la production annuelle en décembre'
    )
    total_pct = fields.Float(
        string='Total (%)',
        compute='_compute_total_pct',
        store=True,
        help='Somme des pourcentages mensuels (doit être égale à 100 %)'
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
                    _('La somme des pourcentages mensuels doit être égale à 100 %%. Total actuel : %.2f %%') % total
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
