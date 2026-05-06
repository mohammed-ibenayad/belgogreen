# -*- coding: utf-8 -*-

import json
import logging
from datetime import timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .staging_rebuild_log import GITHUB_STATE_MAP

_logger = logging.getLogger(__name__)

GITHUB_API = 'https://api.github.com'
HTTP_TIMEOUT = 30
DEFAULT_STAGING_BRANCH = 'staging'
DEFAULT_PRODUCTION_BRANCH = 'production'
DEFAULT_STRATEGY = 'refresh'
DEFAULT_COOLDOWN_MINUTES = 5
PARAM_PREFIX = 'bgg_staging_rebuild.'
# A status/check whose context contains any of these is considered an
# Odoo.sh build status (rather than e.g. an unrelated CI integration).
ODOO_SH_CONTEXT_HINTS = ('odoo.sh', 'odoo-sh', 'odoosh', 'runbot')


class StagingRebuildService(models.AbstractModel):
    """Service that talks to the GitHub API to trigger an Odoo.sh rebuild.

    Odoo.sh rebuilds a tracked branch every time a new commit lands on it.
    We achieve that either by fast-forwarding staging onto production
    (refresh strategy) or by pushing an empty commit on staging
    (empty_commit strategy).
    """
    _name = 'bgg.staging.rebuild.service'
    _description = 'Service de reconstruction Staging'

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
                "La reconstruction Staging n'est pas entièrement configurée. "
                "Veuillez contacter votre administrateur technique."
            ))

        if strategy not in ('refresh', 'empty_commit'):
            raise UserError(_(
                "Configuration invalide. Veuillez contacter votre "
                "administrateur technique."
            ))

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
                "Une reconstruction a déjà été lancée dans les "
                "%s dernière(s) minute(s). Merci de patienter."
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
            raise UserError(_(
                "Connexion au serveur impossible. Merci de réessayer."
            ))
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
                "Branche introuvable. Veuillez contacter votre "
                "administrateur technique."
            ))
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
                "Impossible de préparer la reconstruction. Veuillez "
                "contacter votre administrateur technique."
            ))
        tree_sha = resp.json().get('tree', {}).get('sha')
        if not tree_sha:
            raise UserError(_(
                "Impossible de préparer la reconstruction. Veuillez "
                "contacter votre administrateur technique."
            ))

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
                "Impossible de lancer la reconstruction. Veuillez "
                "contacter votre administrateur technique."
            ))
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
                # Always create a fresh empty commit on top of production.
                # Reason: GitHub's PATCH ref API returns 200 (success) even
                # when the target SHA equals the current SHA, but it does
                # NOT fire a push event in that case — so Odoo.sh would
                # not rebuild. By creating a new commit we guarantee a
                # unique SHA every time, which always triggers a rebuild.
                new_sha = self._create_empty_commit(cfg, source_sha)
                resp = self._update_ref(
                    cfg, cfg['staging_branch'], new_sha, force=True,
                )
                if resp.status_code != 200:
                    raise UserError(_(
                        "La reconstruction n'a pas pu être lancée. "
                        "Veuillez contacter votre administrateur technique."
                    ))
                msg = _(
                    "Reconstruction lancée. Odoo.sh va reconstruire "
                    "l'environnement Staging dans quelques minutes."
                )
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
                        "La reconstruction n'a pas pu être lancée. "
                        "Veuillez contacter votre administrateur technique."
                    ))
                msg = _(
                    "Reconstruction lancée. Odoo.sh va reconstruire "
                    "l'environnement Staging dans quelques minutes."
                )
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

        # Best-effort initial poll so the user sees "Building" right away.
        try:
            self.refresh_log_status(log)
        except Exception:  # noqa: BLE001
            _logger.exception("Initial build-status poll failed")
        return log

    # ------------------------------------------------------- build status API
    @api.model
    def _pick_odoo_sh_status(self, statuses):
        """Pick the most relevant entry from GitHub combined-status statuses[].

        Prefers a context that looks like Odoo.sh; falls back to the first.
        """
        if not statuses:
            return None
        for st in statuses:
            ctx = (st.get('context') or '').lower()
            if any(hint in ctx for hint in ODOO_SH_CONTEXT_HINTS):
                return st
        return statuses[0]

    @api.model
    def _pick_odoo_sh_check_run(self, check_runs):
        if not check_runs:
            return None
        for cr in check_runs:
            name = (cr.get('name') or '').lower()
            app = ((cr.get('app') or {}).get('slug') or '').lower()
            if any(h in name for h in ODOO_SH_CONTEXT_HINTS) \
               or any(h in app for h in ODOO_SH_CONTEXT_HINTS):
                return cr
        return check_runs[0]

    @api.model
    def _fetch_build_state(self, cfg, sha):
        """Return dict with normalized build state for a commit SHA, or None.

        Tries the Check Runs API first (richer, queued/in_progress/completed)
        then falls back to the legacy combined-status endpoint.
        """
        # 1) Check runs
        url = '%s/repos/%s/%s/commits/%s/check-runs' % (
            GITHUB_API, cfg['owner'], cfg['repo'], sha,
        )
        resp = self._request('GET', url, cfg['token'])
        if resp.status_code == 200:
            cr = self._pick_odoo_sh_check_run(
                resp.json().get('check_runs') or [],
            )
            if cr:
                raw = (cr.get('conclusion') or cr.get('status') or '').lower()
                state = GITHUB_STATE_MAP.get(raw, 'unknown')
                return {
                    'state': state,
                    'description': (cr.get('output') or {}).get('title')
                                   or cr.get('status') or '',
                    'url': cr.get('details_url') or cr.get('html_url'),
                    'context': cr.get('name'),
                }

        # 2) Combined status (fallback)
        url = '%s/repos/%s/%s/commits/%s/status' % (
            GITHUB_API, cfg['owner'], cfg['repo'], sha,
        )
        resp = self._request('GET', url, cfg['token'])
        if resp.status_code != 200:
            return None
        data = resp.json()
        st = self._pick_odoo_sh_status(data.get('statuses') or [])
        if not st:
            # No reporter has posted yet — still pending.
            return {
                'state': 'pending',
                'description': _('En attente de la confirmation de Odoo.sh'),
                'url': False,
                'context': False,
            }
        raw = (st.get('state') or '').lower()
        return {
            'state': GITHUB_STATE_MAP.get(raw, 'unknown'),
            'description': st.get('description') or '',
            'url': st.get('target_url'),
            'context': st.get('context'),
        }

    @api.model
    def _fetch_deployment_url(self, cfg, sha):
        """Return the Odoo.sh instance URL for a commit via GitHub Deployments.

        Odoo.sh creates a GitHub Deployment for each staging build and the
        DeploymentStatus carries the freshly-allocated instance URL in its
        ``environment_url`` field, e.g.
        ``https://<slug>-<branch>-<build_id>.dev.odoo.com``.

        This is the only authoritative source GitHub exposes for the new
        build's URL when Odoo.sh's commit-status ``target_url`` only points
        to the branch page (no build_id).
        """
        url = '%s/repos/%s/%s/deployments?sha=%s&per_page=20' % (
            GITHUB_API, cfg['owner'], cfg['repo'], sha,
        )
        resp = self._request('GET', url, cfg['token'])
        if resp.status_code != 200:
            return None
        deployments = resp.json() or []
        # Newest first (GitHub default order); iterate to find the latest
        # status with an environment_url.
        for dep in deployments:
            dep_id = dep.get('id')
            if not dep_id:
                continue
            st_url = '%s/repos/%s/%s/deployments/%s/statuses' % (
                GITHUB_API, cfg['owner'], cfg['repo'], dep_id,
            )
            st_resp = self._request('GET', st_url, cfg['token'])
            if st_resp.status_code != 200:
                continue
            for status in st_resp.json() or []:
                env_url = (status.get('environment_url') or '').strip()
                if env_url:
                    return env_url
        return None

    @api.model
    def refresh_log_status(self, log):
        """Refresh a single log record's build state from GitHub."""
        if not log or not log.commit_sha:
            return False
        cfg = self._read_config()
        info = self._fetch_build_state(cfg, log.commit_sha)
        if not info:
            return False
        vals = {
            'build_state': info['state'],
            'build_description': (info.get('description') or '')[:255],
            'build_url': info.get('url') or log.build_url,
            'build_context': info.get('context') or log.build_context,
            'last_status_check': fields.Datetime.now(),
        }
        if not log.instance_url:
            try:
                env_url = self._fetch_deployment_url(cfg, log.commit_sha)
            except Exception:  # noqa: BLE001
                _logger.exception("GitHub deployments lookup failed")
                env_url = None
            if env_url:
                # Normalize to /odoo so the link opens the backend directly,
                # matching the convention used elsewhere in the module.
                if not env_url.rstrip('/').endswith('/odoo'):
                    env_url = env_url.rstrip('/') + '/odoo'
                vals['instance_url'] = env_url
        log.sudo().write(vals)
        return True
