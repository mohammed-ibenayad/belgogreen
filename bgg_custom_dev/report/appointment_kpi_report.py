# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools


class AppointmentKpiReport(models.Model):
    _name = 'appointment.kpi.report'
    _description = "Rapport KPI Rendez-vous - Avis & Recommandations"
    _auto = False
    _order = 'date desc'

    date = fields.Date(string='Date du rendez-vous', readonly=True)
    user_id = fields.Many2one('res.users', string='Commercial', readonly=True)
    appointment_type_id = fields.Many2one(
        'appointment.type', string='Type de rendez-vous', readonly=True
    )
    appointment_count = fields.Integer(string='Nombre de rendez-vous', readonly=True)
    total_avis = fields.Integer(string='Total avis', readonly=True)
    total_recommandations = fields.Integer(string='Total recommandations', readonly=True)
    avg_avis = fields.Float(
        string='Moy. avis / RDV', readonly=True, group_operator='avg'
    )
    avg_recommandations = fields.Float(
        string='Moy. recommandations / RDV', readonly=True, group_operator='avg'
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    ce.start::date AS date,
                    ru.id AS user_id,
                    ce.appointment_type_id,
                    1 AS appointment_count,
                    COALESCE(ce.x_avis_count, 0) AS total_avis,
                    COALESCE(ce.x_recommandation_count, 0) AS total_recommandations,
                    COALESCE(ce.x_avis_count, 0)::float AS avg_avis,
                    COALESCE(ce.x_recommandation_count, 0)::float AS avg_recommandations
                FROM calendar_event ce
                JOIN calendar_attendee ca ON ca.event_id = ce.id
                JOIN res_partner rp ON rp.id = ca.partner_id
                JOIN res_users ru ON ru.partner_id = rp.id AND ru.active = TRUE
                JOIN res_groups_users_rel grel ON grel.uid = ru.id AND grel.gid = 59
                WHERE ce.appointment_type_id IN (2, 4, 19, 20)
                  AND ce.active = TRUE
            )
        """ % self._table)
