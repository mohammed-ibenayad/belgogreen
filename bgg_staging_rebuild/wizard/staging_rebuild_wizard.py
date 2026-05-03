# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class StagingRebuildWizard(models.TransientModel):
    _name = 'bgg.staging.rebuild.wizard'
    _description = 'Reconstruire le Staging'

    confirm = fields.Boolean(
        string='Je confirme vouloir reconstruire l\'environnement Staging',
    )
    last_log_id = fields.Many2one(
        'bgg.staging.rebuild.log',
        string='Dernière reconstruction',
        readonly=True,
        compute='_compute_last_log',
    )

    @api.depends_context('uid')
    def _compute_last_log(self):
        log = self.env['bgg.staging.rebuild.log'].sudo().search(
            [], order='create_date desc', limit=1,
        )
        for rec in self:
            rec.last_log_id = log.id if log else False

    def action_rebuild(self):
        self.ensure_one()
        if not self.confirm:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'title': _("Confirmation requise"),
                    'message': _("Veuillez cocher la case de confirmation."),
                    'sticky': False,
                },
            }
        log = self.env['bgg.staging.rebuild.service'].trigger_rebuild()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Historique des reconstructions"),
            'res_model': 'bgg.staging.rebuild.log',
            'view_mode': 'list,form',
            'res_id': log.id,
            'target': 'main',
        }
