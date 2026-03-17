# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AppointmentStatusWizard(models.TransientModel):
    _name = 'appointment.status.wizard'
    _description = "Assistant de statut rendez-vous"

    calendar_event_id = fields.Many2one(
        'calendar.event', string='Rendez-vous', required=True
    )
    new_status = fields.Selection([
        ('booked', 'Booked'),
        ('no_show', 'No Show'),
        ('attended', 'Attended'),
    ], string='Nouveau statut', required=True)
    x_avis_count = fields.Integer(
        string="Nombre d'avis récoltés", default=0
    )
    x_recommandation_count = fields.Integer(
        string='Nombre de recommandations', default=0
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            event = self.env['calendar.event'].browse(self.env.context['active_id'])
            res['calendar_event_id'] = event.id
            res['x_avis_count'] = event.x_avis_count
            res['x_recommandation_count'] = event.x_recommandation_count
        return res

    def action_confirm(self):
        self.ensure_one()
        self.calendar_event_id.write({
            'appointment_status': self.new_status,
            'x_avis_count': self.x_avis_count,
            'x_recommandation_count': self.x_recommandation_count,
        })
        return {'type': 'ir.actions.client', 'tag': 'reload'}
