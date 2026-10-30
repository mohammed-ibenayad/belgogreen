# -*- coding: utf-8 -*-

from odoo import fields, models


class BggRdvNeed(models.Model):
    """Answers of the "Besoin" question of the booking questionnaire
    (e.g. Panneaux, Batterie, PAC, Isolation)."""
    _name = 'bgg.rdv.need'
    _description = 'Besoin du client (prise de RDV)'
    _order = 'sequence, id'

    name = fields.Char(string='Besoin', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
