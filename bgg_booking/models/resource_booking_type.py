# -*- coding: utf-8 -*-

from odoo import fields, models


class ResourceBookingType(models.Model):
    _inherit = 'resource.booking.type'

    x_rdv_type_id = fields.Many2one(
        'bgg.rdv.type',
        string='Type de RDV',
        help="Type de RDV donné aux rendez-vous pris avec ce type de réservation "
             "(règles call center / commercial, tableaux de bord).",
    )
