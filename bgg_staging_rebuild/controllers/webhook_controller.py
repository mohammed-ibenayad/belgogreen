# -*- coding: utf-8 -*-

import hashlib
import hmac
import json
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Map raw Odoo.sh build status / result strings to our normalized state.
ODOOSH_STATE_MAP = {
    'building': 'building',
    'started': 'building',
    'updating': 'building',
    'queued': 'building',
    'pending': 'pending',
    'success': 'success',
    'failed': 'failure',
    'failure': 'failure',
    'error': 'failure',
    'warning': 'success',
}


class StagingRebuildWebhookController(http.Controller):
    """Public endpoint that Odoo.sh hits on every build event.

    Configure on Odoo.sh side: Project -> Settings -> Webhooks
        URL:    https://<odoo-instance>/bgg_staging_rebuild/webhook/odoosh
        Secret: same value as `bgg_staging_rebuild.webhook_secret`
        Events: build start / update / done

    The controller is inert until the system parameter is set: any request
    received while the secret is empty returns 503.
    """

    @http.route(
        '/bgg_staging_rebuild/webhook/odoosh',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def receive_odoosh_webhook(self, **_kwargs):
        raw_body = request.httprequest.get_data() or b''
        env = request.env(su=True)

        secret = (env['ir.config_parameter'].get_param(
            'bgg_staging_rebuild.webhook_secret', '',
        ) or '').strip()
        if not secret:
            _logger.warning(
                "Odoo.sh webhook received but no secret is configured; "
                "ignoring. Set ir.config_parameter "
                "'bgg_staging_rebuild.webhook_secret' to enable."
            )
            return self._plain('Webhook not configured', status=503)

        if not self._authenticate(secret, raw_body):
            _logger.warning("Odoo.sh webhook: authentication failed")
            return self._plain('Forbidden', status=403)

        try:
            payload = json.loads(raw_body.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return self._plain('Invalid JSON', status=400)

        commit_sha = self._extract_sha(payload)
        if not commit_sha:
            _logger.info(
                "Odoo.sh webhook without commit SHA, payload=%s",
                json.dumps(payload)[:500],
            )
            return self._plain('OK (no SHA in payload)', status=200)

        info = self._extract_build_info(payload)

        log = env['bgg.staging.rebuild.log'].search(
            [('commit_sha', '=', commit_sha)], limit=1,
        )
        if not log:
            _logger.info(
                "Odoo.sh webhook for unknown SHA %s, skipping", commit_sha,
            )
            return self._plain('OK (no matching log)', status=200)

        vals = {
            'build_state': info['state'],
            'build_description': (info['description'] or '')[:255],
            'build_context': info['context'] or 'odoo.sh-webhook',
            'last_status_check': fields.Datetime.now(),
        }
        if info['url']:
            vals['build_url'] = info['url']
        log.write(vals)

        _logger.info(
            "Odoo.sh webhook: log %s SHA %s -> state=%s",
            log.id, commit_sha[:8], info['state'],
        )
        return self._plain('OK', status=200)

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _plain(body, status=200):
        return request.make_response(
            body,
            headers=[('Content-Type', 'text/plain; charset=utf-8')],
            status=status,
        )

    @staticmethod
    def _authenticate(secret, raw_body):
        """Accept either an HMAC-SHA256 signature or a plain shared-secret
        header. Tries the headers Odoo.sh / GitHub / generic webhook senders
        commonly use."""
        headers = request.httprequest.headers

        signature_headers = (
            'X-Odoo-Signature',
            'X-Odoo-Sh-Signature',
            'X-Hub-Signature-256',
            'X-Webhook-Signature',
        )
        plain_headers = (
            'X-Webhook-Secret',
            'X-Odoo-Token',
            'X-Odoo-Sh-Token',
            'Authorization',
        )

        expected = hmac.new(
            secret.encode('utf-8'), raw_body, hashlib.sha256,
        ).hexdigest()
        for header in signature_headers:
            provided = (headers.get(header) or '').strip()
            if not provided:
                continue
            if provided.startswith('sha256='):
                provided = provided[7:]
            if hmac.compare_digest(provided, expected):
                return True

        for header in plain_headers:
            provided = (headers.get(header) or '').strip()
            if provided.startswith('Bearer '):
                provided = provided[7:]
            if provided and hmac.compare_digest(provided, secret):
                return True

        return False

    @staticmethod
    def _extract_sha(payload):
        commit = payload.get('commit') if isinstance(payload, dict) else None
        build = payload.get('build') if isinstance(payload, dict) else None
        head = payload.get('head_commit') if isinstance(payload, dict) else None
        candidates = [
            (commit or {}).get('id') if isinstance(commit, dict) else None,
            (commit or {}).get('sha') if isinstance(commit, dict) else None,
            payload.get('commit_id') if isinstance(payload, dict) else None,
            payload.get('sha') if isinstance(payload, dict) else None,
            (build or {}).get('commit_id') if isinstance(build, dict) else None,
            ((build or {}).get('commit') or {}).get('id')
                if isinstance(build, dict) else None,
            (head or {}).get('id') if isinstance(head, dict) else None,
        ]
        return next((c for c in candidates if c), None)

    @staticmethod
    def _extract_build_info(payload):
        build = payload.get('build') if isinstance(payload, dict) else {}
        if not isinstance(build, dict):
            build = {}

        status = (build.get('status') or payload.get('status') or '').lower()
        result = (build.get('result') or payload.get('result') or '').lower()
        url = (
            build.get('url')
            or build.get('frontend_url')
            or build.get('html_url')
            or payload.get('url')
        )
        description = (
            build.get('message')
            or build.get('name')
            or payload.get('event')
            or status
            or 'Updated'
        )

        if status in ('done', 'completed', 'finished'):
            if result in ('success', 'ok', 'pass'):
                state = 'success'
            elif result in ('failure', 'failed', 'ko', 'error'):
                state = 'failure'
            else:
                state = 'success'
        else:
            state = ODOOSH_STATE_MAP.get(status, 'unknown')

        return {
            'state': state,
            'description': description,
            'url': url,
            'context': 'odoo.sh-webhook',
        }
