# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StagingRebuildLog(models.Model):
    _name = 'bgg.staging.rebuild.log'
    _description = 'Staging Rebuild Audit Log'
    _order = 'create_date desc'
    _rec_name = 'create_date'

    user_id = fields.Many2one(
        'res.users',
        string='Triggered By',
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
    )
    strategy = fields.Selection(
        [('refresh', 'Refresh staging from production'),
         ('empty_commit', 'Empty commit on staging')],
        string='Strategy',
        readonly=True,
    )
    branch = fields.Char(string='Target Branch', readonly=True)
    source_branch = fields.Char(string='Source Branch', readonly=True)
    commit_sha = fields.Char(string='Resulting Commit SHA', readonly=True)
    status = fields.Selection(
        [('success', 'Success'),
         ('error', 'Error')],
        string='Status',
        readonly=True,
    )
    http_status = fields.Integer(string='HTTP Status', readonly=True)
    message = fields.Text(string='Message', readonly=True)

    @api.model
    def log_attempt(self, strategy, branch, source_branch, status,
                    http_status=False, commit_sha=False, message=False):
        return self.sudo().create({
            'strategy': strategy,
            'branch': branch,
            'source_branch': source_branch,
            'status': status,
            'http_status': http_status or 0,
            'commit_sha': commit_sha or False,
            'message': (message or '')[:4000],
        })
