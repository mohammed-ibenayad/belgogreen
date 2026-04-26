# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class StagingRebuildWizard(models.TransientModel):
    _name = 'bgg.staging.rebuild.wizard'
    _description = 'Rebuild Staging (Wizard)'

    confirm = fields.Boolean(
        string='I understand this will overwrite the staging environment',
        help="Required to enable the rebuild button.",
    )
    strategy_preview = fields.Char(
        string='Strategy',
        readonly=True,
        compute='_compute_preview',
    )
    staging_branch_preview = fields.Char(
        string='Staging Branch',
        readonly=True,
        compute='_compute_preview',
    )
    production_branch_preview = fields.Char(
        string='Production Branch',
        readonly=True,
        compute='_compute_preview',
    )
    last_log_id = fields.Many2one(
        'bgg.staging.rebuild.log',
        string='Last Rebuild',
        readonly=True,
        compute='_compute_last_log',
    )

    @api.depends_context('uid')
    def _compute_preview(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        for rec in self:
            rec.strategy_preview = get(
                'bgg_staging_rebuild.strategy', 'refresh',
            )
            rec.staging_branch_preview = get(
                'bgg_staging_rebuild.staging_branch', 'staging',
            )
            rec.production_branch_preview = get(
                'bgg_staging_rebuild.production_branch', 'production',
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
                    'title': _("Confirmation required"),
                    'message': _("Tick the confirmation box before rebuilding."),
                    'sticky': False,
                },
            }
        log = self.env['bgg.staging.rebuild.service'].trigger_rebuild()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _("Staging rebuild triggered"),
                'message': log.message or _("Odoo.sh will rebuild shortly."),
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'bgg.staging.rebuild.log',
                    'view_mode': 'list,form',
                    'name': _("Staging Rebuild Logs"),
                },
            },
        }
