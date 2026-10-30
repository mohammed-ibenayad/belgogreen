# -*- coding: utf-8 -*-
"""Stages of the SSS projects, second pass (19.0.2.3.1).

The first pass (19.0.2.3.0) could not move the tasks of the SSS projects
that had no "SSS: À faire" stage (older projects made in Field Service).
They get their two SSS stages now, then the same cleanup runs again. Safe
to run several times.
"""
from odoo import SUPERUSER_ID, api
from odoo.tools import sql

from odoo.addons.bgg_custom_dev.hooks import fix_sss_stages


def migrate(cr, version):
    if not version or not sql.column_exists(cr, 'project_project', 'x_is_sss_project'):
        return
    fix_sss_stages(api.Environment(cr, SUPERUSER_ID, {}))
