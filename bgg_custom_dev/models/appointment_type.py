# -*- coding: utf-8 -*-

from odoo import fields, models


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    x_appointment_ref = fields.Char(
        string='Appointment Reference',
        help='Business reference code for this appointment type (e.g., APT-ENERG-CNT, APT-NISOL-COM)',
        index=True,
    )
