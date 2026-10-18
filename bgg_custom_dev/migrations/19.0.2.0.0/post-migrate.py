# -*- coding: utf-8 -*-
"""Install the Enterprise bridge (bgg_custom_dev_ee) when Enterprise
Appointments is installed, so the RDV and SSS fields stay in sync with
Enterprise until it is removed. Odoo loads the module in this same run."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Module = env['ir.module.module']
    if not Module.search_count([('name', '=', 'appointment'), ('state', '=', 'installed')]):
        return
    bridge = Module.search([('name', '=', 'bgg_custom_dev_ee'), ('state', '=', 'uninstalled')])
    if bridge:
        bridge.button_install()
        _logger.info("bgg_custom_dev: Enterprise bridge bgg_custom_dev_ee marked for installation")
