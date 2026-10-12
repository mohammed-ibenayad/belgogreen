# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, SUPERUSER_ID
from odoo.addons.bgg_custom_dev.models.sale_order import (
    ADMIN_DEADLINE_RULES_PARAM, upgrade_admin_deadline_rules,
)

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Rule change: admin project end = SSS reference end + 'end_offset'
    (10 business days) instead of start + per-category delay.

    1. The rules parameter is noupdate: convert the stored value in place
       (per-category delays dropped, 'end_offset' added) so the 'sss' values
       an admin may have changed are kept. A missing or invalid value is left
       alone: the code then uses its built-in defaults.
    2. Recompute the dates of the admin projects of every confirmed order
       (project start/end and the dates of their open tasks)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    params = env['ir.config_parameter'].sudo()
    raw = params.get_param(ADMIN_DEADLINE_RULES_PARAM)
    try:
        rules = json.loads(raw) if raw else None
    except ValueError:
        rules = None
    if isinstance(rules, dict):
        params.set_param(
            ADMIN_DEADLINE_RULES_PARAM,
            json.dumps(upgrade_admin_deadline_rules(rules), ensure_ascii=False, indent=2))
    else:
        _logger.warning("Dossier: parameter %s missing or not a JSON object, "
                        "not converted (built-in defaults apply).", ADMIN_DEADLINE_RULES_PARAM)

    orders = env['sale.order']._get_admin_dossier_orders()
    orders._recompute_admin_project_dates()
