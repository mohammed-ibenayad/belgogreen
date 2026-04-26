# -*- coding: utf-8 -*-

import json
import logging
from datetime import timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GITHUB_API = 'https://api.github.com'
HTTP_TIMEOUT = 30
DEFAULT_STAGING_BRANCH = 'staging'
DEFAULT_PRODUCTION_BRANCH = 'production'
DEFAULT_STRATEGY = 'refresh'
DEFAULT_COOLDOWN_MINUTES = 5
PARAM_PREFIX = 'bgg_staging_rebuild.'


class StagingRebuildService(models.AbstractModel):
    """Service that talks to the GitHub API to trigger an Odoo.sh rebuild.

    Odoo.sh rebuilds a tracked branch every time a new commit lands on it.
    We achieve that either by fast-forwarding staging onto production
    (refresh strategy) or by pushing an empty commit on staging
    (empty_commit strategy).
    """
    _name = 'bgg.staging.rebuild.service'
    _description = 'Staging Rebuild Service'

    # ---------------------------------------------------------------- helpers
    @api.model
    def _get_param(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(
            PARAM_PREFIX + key, default,
        )

    @api.model
    def _read_config(self):
        get = self._get_param
        owner = (get('github_owner') or '').strip()
        repo = (get('github_repo') or '').strip()
        token = (get('github_token') or '').strip()
        staging_branch = (get('staging_branch') or DEFAULT_STAGING_BRANCH).strip()
        production_branch = (get('production_branch') or DEFAULT_PRODUCTION_BRANCH).strip()
        strategy = (get('strategy') or DEFAULT_STRATEGY).strip()
        try:
            cooldown = int(get('cooldown_minutes') or DEFAULT_COOLDOWN_MINUTES)
        except (TypeError, ValueError):
            cooldown = DEFAULT_COOLDOWN_MINUTES

        missing = [k for k, v in (
            ('github_owner', owner),
            ('github_repo', repo),
            ('github_token', token),
        ) if not v]
        if missing:
            raise UserError(_(
                "Staging rebuild is not fully configured. Missing system "
                "parameter(s): %s"
            ) % ', '.join(PARAM_PREFIX + m for m in missing))

        if strategy not in ('refresh', 'empty_commit'):
            raise UserError(_(
                "Invalid strategy '%s'. Use 'refresh' or 'empty_commit'."
            ) % strategy)

        return {
            'owner': owner,
            'repo': repo,
            'token': token,
            'staging_branch': staging_branch,
            'production_branch': production_branch,
            'strategy': strategy,
            'cooldown': cooldown,
        }

    @api.model
    def _headers(self, token):
        return {
            'Accept': 'application/vnd.github+json',
            'Authorization': 'Bearer %s' % token,
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'belgogreen-staging-rebuild',
        }

    @api.model
    def _enforce_cooldown(self, cooldown_minutes):
        if cooldown_minutes <= 0:
            return
        threshold = fields.Datetime.now() - timedelta(minutes=cooldown_minutes)
        recent = self.env['bgg.staging.rebuild.log'].sudo().search_count([
            ('status', '=', 'success'),
            ('create_date', '>=', threshold),
        ])
        if recent:
            raise UserError(_(
                "A rebuild was already triggered in the last %s minute(s). "
                "Please wait before retrying."
            ) % cooldown_minutes)

    @api.model
    def _request(self, method, url, token, payload=None):
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(token),
                data=json.dumps(payload) if payload is not None else None,
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            _logger.exception("GitHub %s %s failed", method, url)
            raise UserError(_("GitHub request failed: %s") % exc)
        return response

    # --------------------------------------------------------------- API calls
    @api.model
    def _get_branch_sha(self, cfg, branch):
        url = '%s/repos/%s/%s/git/ref/heads/%s' % (
            GITHUB_API, cfg['owner'], cfg['repo'], branch,
        )
        resp = self._request('GET', url, cfg['token'])
        if resp.status_code != 200:
            raise UserError(_(
                "Could not read branch '%s' (HTTP %s): %s"
            ) % (branch, resp.status_code, resp.text[:500]))
        return resp.json().get('object', {}).get('sha')

    @api.model
    def _update_ref(self, cfg, branch, sha, force=False):
        url = '%s/repos/%s/%s/git/refs/heads/%s' % (
            GITHUB_API, cfg['owner'], cfg['repo'], branch,
        )
        return self._request('PATCH', url, cfg['token'], {
            'sha': sha,
            'force': force,
        })

    @api.model
    def _create_empty_commit(self, cfg, parent_sha):
        url_commit = '%s/repos/%s/%s/git/commits/%s' % (
            GITHUB_API, cfg['owner'], cfg['repo'], parent_sha,
        )
        resp = self._request('GET', url_commit, cfg['token'])
        if resp.status_code != 200:
            raise UserError(_(
                "Could not read parent commit (HTTP %s): %s"
            ) % (resp.status_code, resp.text[:500]))
        tree_sha = resp.json().get('tree', {}).get('sha')
        if not tree_sha:
            raise UserError(_("Parent commit has no tree SHA."))

        url_create = '%s/repos/%s/%s/git/commits' % (
            GITHUB_API, cfg['owner'], cfg['repo'],
        )
        message = 'chore(staging): rebuild triggered from Odoo by %s' % (
            self.env.user.login,
        )
        resp = self._request('POST', url_create, cfg['token'], {
            'message': message,
            'tree': tree_sha,
            'parents': [parent_sha],
        })
        if resp.status_code not in (200, 201):
            raise UserError(_(
                "Could not create empty commit (HTTP %s): %s"
            ) % (resp.status_code, resp.text[:500]))
        return resp.json().get('sha')

    # ----------------------------------------------------------------- public
    @api.model
    def trigger_rebuild(self):
        """Entry point. Returns the created log record."""
        cfg = self._read_config()
        self._enforce_cooldown(cfg['cooldown'])

        log_model = self.env['bgg.staging.rebuild.log']

        try:
            if cfg['strategy'] == 'refresh':
                source_sha = self._get_branch_sha(cfg, cfg['production_branch'])
                resp = self._update_ref(
                    cfg, cfg['staging_branch'], source_sha, force=True,
                )
                if resp.status_code != 200:
                    raise UserError(_(
                        "Could not update staging branch (HTTP %s): %s"
                    ) % (resp.status_code, resp.text[:500]))
                new_sha = resp.json().get('object', {}).get('sha') or source_sha
                msg = _(
                    "Staging branch '%(staging)s' fast-forwarded to "
                    "production '%(prod)s' (sha %(sha)s). Odoo.sh will rebuild."
                ) % {
                    'staging': cfg['staging_branch'],
                    'prod': cfg['production_branch'],
                    'sha': new_sha[:8] if new_sha else '?',
                }
                log = log_model.log_attempt(
                    strategy='refresh',
                    branch=cfg['staging_branch'],
                    source_branch=cfg['production_branch'],
                    status='success',
                    http_status=resp.status_code,
                    commit_sha=new_sha,
                    message=msg,
                )
            else:
                parent_sha = self._get_branch_sha(cfg, cfg['staging_branch'])
                new_sha = self._create_empty_commit(cfg, parent_sha)
                resp = self._update_ref(
                    cfg, cfg['staging_branch'], new_sha, force=False,
                )
                if resp.status_code != 200:
                    raise UserError(_(
                        "Could not move staging ref (HTTP %s): %s"
                    ) % (resp.status_code, resp.text[:500]))
                msg = _(
                    "Empty commit %(sha)s pushed to '%(staging)s'. "
                    "Odoo.sh will rebuild."
                ) % {
                    'sha': new_sha[:8] if new_sha else '?',
                    'staging': cfg['staging_branch'],
                }
                log = log_model.log_attempt(
                    strategy='empty_commit',
                    branch=cfg['staging_branch'],
                    source_branch=cfg['staging_branch'],
                    status='success',
                    http_status=resp.status_code,
                    commit_sha=new_sha,
                    message=msg,
                )
        except UserError as exc:
            log_model.log_attempt(
                strategy=cfg['strategy'],
                branch=cfg['staging_branch'],
                source_branch=cfg.get('production_branch'),
                status='error',
                message=str(exc),
            )
            raise

        _logger.info(
            "Staging rebuild triggered by %s (strategy=%s, sha=%s)",
            self.env.user.login, cfg['strategy'], log.commit_sha,
        )
        return log
