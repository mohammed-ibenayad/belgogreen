# -*- coding: utf-8 -*-

from odoo import fields, models


class BggRdvType(models.Model):
    """Appointment (RDV) type, owned by this module.

    Replaces the Enterprise ``appointment.type`` for everything the business
    logic needs (the reference code that drives the call-center / commercial
    rules). Existing types are copied over with their ids by the 19.0.2.0.0
    migration; while Enterprise Appointments is installed, the bridge module
    bgg_custom_dev_ee keeps each appointment type linked to its RDV type.
    """
    _name = 'bgg.rdv.type'
    _description = 'Type de rendez-vous'
    _order = 'sequence, name, id'

    name = fields.Char(string='Nom', required=True)
    code = fields.Char(
        string='Référence',
        index=True,
        copy=False,
        help='Code métier du type (ex. APT-ENERG-CNT, APT-NISOL-COM). '
             'Les règles call center / commercial se basent sur ce code.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'Cette référence de type de rendez-vous existe déjà.',
    )
