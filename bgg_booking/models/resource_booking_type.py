# -*- coding: utf-8 -*-

from odoo import fields, models


class ResourceBookingType(models.Model):
    """BelGoGreen settings of a booking type: its RDV type and which
    questions of the call-centre questionnaire it asks (as the former
    Appointments types did)."""
    _inherit = 'resource.booking.type'

    x_rdv_type_id = fields.Many2one(
        'bgg.rdv.type',
        string='Type de RDV',
        help="Type de RDV donné aux rendez-vous pris avec ce type de réservation "
             "(règles call center / commercial, tableaux de bord).",
    )
    x_need_ids = fields.Many2many(
        'bgg.rdv.need',
        string='Besoins proposés',
        help="Réponses proposées à la question « Besoin ».",
    )
    x_need_multiple = fields.Boolean(
        string='Plusieurs besoins',
        help="Coché : plusieurs besoins possibles. Sinon un seul.",
    )
    x_ask_solar_since = fields.Boolean(
        string='Question « panneaux depuis »',
        help="Demander depuis combien de temps les clients ont des panneaux solaires (obligatoire).",
    )
    x_ask_sms_confirmation = fields.Boolean(string='Question « confirmation par SMS »')
    x_ask_on_behalf = fields.Boolean(
        string='Question « pris à la place de »',
        help="Types call center : agent pour qui le RDV est pris.",
    )
    x_create_opportunity = fields.Boolean(
        string='Créer une opportunité',
        default=True,
        help="Une opportunité CRM est créée pour chaque RDV et liée à l'événement "
             "(attribution de la vente au call center).",
    )
