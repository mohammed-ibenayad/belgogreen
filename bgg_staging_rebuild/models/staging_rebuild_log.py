# -*- coding: utf-8 -*-

import re

from odoo import _, api, fields, models

# Mapping from raw GitHub commit-status states to our normalized states.
# GitHub combined status: pending | success | failure | error
# Check runs status:      queued | in_progress | completed
# Check runs conclusion:  success | failure | neutral | cancelled | skipped |
#                         timed_out | action_required
GITHUB_STATE_MAP = {
    'pending': 'building',
    'queued': 'building',
    'in_progress': 'building',
    'success': 'success',
    'failure': 'failure',
    'error': 'failure',
    'cancelled': 'failure',
    'timed_out': 'failure',
    'action_required': 'failure',
    'neutral': 'success',
    'skipped': 'success',
}


class StagingRebuildLog(models.Model):
    _name = 'bgg.staging.rebuild.log'
    _description = 'Historique des reconstructions Staging'
    _order = 'create_date desc'
    _rec_name = 'create_date'

    user_id = fields.Many2one(
        'res.users',
        string='Lancée par',
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
    )
    strategy = fields.Selection(
        [('refresh', 'Synchronisation depuis la production'),
         ('empty_commit', 'Reconstruction simple')],
        string='Type',
        readonly=True,
    )
    branch = fields.Char(string='Branche cible', readonly=True)
    source_branch = fields.Char(string='Branche source', readonly=True)
    commit_sha = fields.Char(string='Identifiant du commit', readonly=True)
    status = fields.Selection(
        [('success', 'Demande envoyée'),
         ('error', 'Erreur')],
        string='Envoi',
        readonly=True,
    )
    http_status = fields.Integer(string='Code HTTP', readonly=True)
    message = fields.Text(string='Message technique', readonly=True)

    # ---- Build tracking (populated by polling GitHub commit statuses) -------
    build_state = fields.Selection(
        [('pending', 'En attente'),
         ('building', 'Reconstruction en cours'),
         ('success', 'Reconstruction réussie'),
         ('failure', 'Échec'),
         ('unknown', 'Inconnu')],
        string='État',
        default='pending',
        readonly=True,
    )
    build_description = fields.Char(string='Détail', readonly=True)
    build_url = fields.Char(string='Lien du build', readonly=True)
    build_context = fields.Char(string='Contexte', readonly=True)
    last_status_check = fields.Datetime(
        string='Dernière vérification', readonly=True,
    )
    database_url = fields.Char(
        string='Lien du Staging',
        compute='_compute_database_url',
    )

    @api.depends('build_url', 'branch')
    def _compute_database_url(self):
        fallback = (self.env['ir.config_parameter'].sudo().get_param(
            'bgg_staging_rebuild.staging_url') or '').strip()
        for rec in self:
            rec.database_url = self._build_database_url(
                rec.build_url, rec.branch,
            ) or fallback or False

    @staticmethod
    def _build_database_url(build_url, branch):
        """Construct the Odoo.sh staging instance URL from the build URL.

        Odoo.sh build URLs include the project slug and build id, e.g.
            https://www.odoo.sh/project/<slug>/builds/<build_id>
            https://www.odoo.sh/project/<slug>/branches/<branch>/build/<build_id>
        The instance follows
            https://<slug>-<branch>-<build_id>.dev.odoo.com/odoo
        Returns False if either piece can't be extracted.
        """
        if not build_url or not branch:
            return False
        slug = re.search(r'/project/([^/]+)/', build_url)
        build_id = re.search(r'/builds?/(\d+)', build_url)
        if not slug or not build_id:
            return False
        return 'https://%s-%s-%s.dev.odoo.com/odoo' % (
            slug.group(1), branch, build_id.group(1),
        )

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
            'build_state': 'pending' if status == 'success' else 'unknown',
        })

    # ---- Status refresh ------------------------------------------------------
    def action_refresh_status(self):
        for rec in self:
            if rec.commit_sha and rec.status == 'success':
                self.env['bgg.staging.rebuild.service'].refresh_log_status(rec)
        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def action_open_build(self):
        self.ensure_one()
        if not self.build_url:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': self.build_url,
            'target': 'new',
        }

    def action_open_staging(self):
        self.ensure_one()
        if not self.database_url:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': self.database_url,
            'target': 'new',
        }

    @api.model
    def action_open_rebuild_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reconstruire le Staging'),
            'res_model': 'bgg.staging.rebuild.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def _cron_refresh_active_builds(self):
        """Refresh build state for recent triggers that aren't terminal yet."""
        from datetime import timedelta
        threshold = fields.Datetime.now() - timedelta(hours=1)
        active = self.search([
            ('status', '=', 'success'),
            ('create_date', '>=', threshold),
            ('build_state', 'in', ('pending', 'building', 'unknown')),
            ('commit_sha', '!=', False),
        ])
        service = self.env['bgg.staging.rebuild.service']
        for rec in active:
            try:
                service.refresh_log_status(rec)
            except Exception:  # noqa: BLE001
                # Cron must not crash; the service already logs.
                continue
