# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class AvisCountReport(models.Model):
    _name = 'avis.count.report'
    _description = "Rapport Avis & Recommandations"
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
    x_avis_count = fields.Integer(string="Nombre d'avis", readonly=True)
    x_recommandation_count = fields.Integer(string='Nombre de recommandations', readonly=True)

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
                    COALESCE(ce.x_avis_count, 0) AS x_avis_count,
                    COALESCE(ce.x_recommandation_count, 0) AS x_recommandation_count
                FROM calendar_event ce
                JOIN appointment_type apt ON apt.id = ce.appointment_type_id
                WHERE apt.x_appointment_ref IN ('APT-ENERG-CNT', 'APT-NISOL-CNT', 'APT-ENERG-COM', 'APT-NISOL-COM')
                  AND ce.user_id IS NOT NULL
            )
        """ % self._table)
