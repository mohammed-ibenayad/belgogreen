# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools


class CommercialKpiReport(models.Model):
    _name = 'commercial.kpi.report'
    _description = "Rapport KPI Suivi Commercial"
    _auto = False
    _order = 'date desc'

    date = fields.Date(string='Date du rendez-vous', readonly=True)
    user_id = fields.Many2one('res.users', string='Commercial', readonly=True)
    appointment_type_id = fields.Many2one(
        'appointment.type', string='Type de rendez-vous', readonly=True
    )
    appointment_category = fields.Selection([
        ('call', 'RDV Call'),
        ('commercial', 'RDV Commercial'),
    ], string='Catégorie', readonly=True)
    appointment_status = fields.Selection([
        ('attended', 'Présent'),
        ('no_show', 'No-Show'),
        ('cancelled', 'Refusé'),
        ('booked', 'Réservé'),
    ], string='Statut', readonly=True)
    appointment_count = fields.Integer(string='Nombre de RDV', readonly=True)
    attended_count = fields.Integer(string='Présents', readonly=True)
    no_show_count = fields.Integer(string='No-Show', readonly=True)
    cancelled_count = fields.Integer(string='Refusés', readonly=True)
    booked_count = fields.Integer(string='Réservés', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    ce.start::date AS date,
                    ce.user_id AS user_id,
                    ce.appointment_type_id,
                    CASE
                        WHEN apt.x_appointment_ref IN ('APT-ENERG-CNT', 'APT-NISOL-CNT') THEN 'call'
                        WHEN apt.x_appointment_ref IN ('APT-ENERG-COM', 'APT-NISOL-COM') THEN 'commercial'
                    END AS appointment_category,
                    ce.appointment_status,
                    1 AS appointment_count,
                    CASE WHEN ce.appointment_status = 'attended' THEN 1 ELSE 0 END AS attended_count,
                    CASE WHEN ce.appointment_status = 'no_show' THEN 1 ELSE 0 END AS no_show_count,
                    CASE WHEN ce.appointment_status = 'cancelled' THEN 1 ELSE 0 END AS cancelled_count,
                    CASE WHEN ce.appointment_status = 'booked' THEN 1 ELSE 0 END AS booked_count
                FROM calendar_event ce
                JOIN appointment_type apt ON apt.id = ce.appointment_type_id
                WHERE apt.x_appointment_ref IN ('APT-ENERG-CNT', 'APT-NISOL-CNT', 'APT-ENERG-COM', 'APT-NISOL-COM')
                  AND ce.active = TRUE
                  AND ce.user_id IS NOT NULL
            )
        """ % self._table)
