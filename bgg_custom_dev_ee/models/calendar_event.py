# -*- coding: utf-8 -*-

from odoo import api, models

# Statuses shared by Enterprise appointment_status and bgg_custom_dev x_rdv_status
SYNCED_STATUSES = {'request', 'booked', 'attended', 'no_show', 'cancelled'}


class CalendarEvent(models.Model):
    """Keep the bgg_custom_dev RDV fields in sync with Enterprise Appointments.

    - appointment_type_id -> x_rdv_type_id (through the appointment type's
      linked RDV type)
    - appointment_status <-> x_rdv_status (the bgg_custom_dev rules write the
      status too, e.g. a rescheduled no-show goes back to booked)

    The values are translated inside the same create / write call, before the
    bgg_custom_dev overrides run, so its rules see the RDV fields directly.
    """
    _inherit = 'calendar.event'

    @api.model
    def _bgg_rdv_type_for(self, appointment_type_id):
        if not appointment_type_id:
            return False
        atype = self.env['appointment.type'].sudo().browse(appointment_type_id).exists()
        return atype._bgg_ensure_rdv_type().id if atype else False

    @api.model
    def _bgg_sync_rdv_vals(self, vals):
        """Mirror the Enterprise appointment fields and the RDV fields in vals."""
        if 'appointment_type_id' in vals and 'x_rdv_type_id' not in vals:
            vals['x_rdv_type_id'] = self._bgg_rdv_type_for(vals['appointment_type_id'])
        if 'appointment_status' in vals and 'x_rdv_status' not in vals:
            status = vals['appointment_status']
            vals['x_rdv_status'] = status if status in SYNCED_STATUSES else False
        elif 'x_rdv_status' in vals and 'appointment_status' not in vals:
            if vals['x_rdv_status'] in SYNCED_STATUSES:
                vals['appointment_status'] = vals['x_rdv_status']
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._bgg_sync_rdv_vals(vals)
        records = super().create(vals_list)
        # The appointment status may come from its default (not in vals):
        # copy whatever Enterprise ended up with.
        missing = records.filtered(
            lambda e: e.appointment_type_id and not e.x_rdv_status
            and e.appointment_status in SYNCED_STATUSES)
        for event in missing:
            event.with_context(skip_calendar_automation=True).write(
                {'x_rdv_status': event.appointment_status})
        return records

    def write(self, vals):
        self._bgg_sync_rdv_vals(vals)
        return super().write(vals)

    def _bgg_refresh_rdv_answers(self):
        """Summary of the booking questionnaire on the event
        ("Question : réponse" lines), kept after Enterprise is removed."""
        AnswerInput = self.env['appointment.answer.input'].sudo()
        for event in self:
            inputs = AnswerInput.search([('calendar_event_id', '=', event.id)])
            inputs = inputs.sorted(lambda a: (a.question_id.sequence, a.question_id.id, a.id))
            lines = []
            for answer in inputs:
                value = answer.value_text_box or answer.value_answer_id.name or ''
                if value:
                    lines.append('%s : %s' % (answer.question_id.name, value))
            summary = '\n'.join(lines) or False
            if event.x_rdv_answers != summary:
                event.sudo().with_context(skip_calendar_automation=True).write(
                    {'x_rdv_answers': summary})
