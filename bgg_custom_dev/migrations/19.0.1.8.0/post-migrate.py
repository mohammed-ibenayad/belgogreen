# -*- coding: utf-8 -*-

import json

from odoo import api, SUPERUSER_ID
from odoo.addons.bgg_custom_dev.models.sale_order import (
    ADMIN_DEADLINE_RULES_DEFAULT, ADMIN_DEADLINE_RULES_PARAM,
)


def migrate(cr, version):
    """Rule change: business days everywhere (no more calendar days for the
    financing terms) and the new 'sss' reference block. The parameter is
    noupdate, so overwrite it with the new defaults on upgrade. The task
    rules parameter is new and is created by the data file."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.config_parameter'].sudo().set_param(
        ADMIN_DEADLINE_RULES_PARAM,
        json.dumps(ADMIN_DEADLINE_RULES_DEFAULT, ensure_ascii=False, indent=2))
