# -*- coding: utf-8 -*-

from . import models
from . import report
from . import controllers

import logging
_logger = logging.getLogger(__name__)


def _assign_admin_group_to_menus(env):
    """Find the existing 'Admin' group and restrict dashboard menus to it."""
    admin_group = env['res.groups'].search([('name', '=', 'Admin')], limit=1)
    if not admin_group:
        _logger.warning("No 'Admin' group found. Dashboard menus will remain unrestricted.")
        return

    menu_xmlids = [
        'bgg_custom_dev.menu_bgg_custom_dev_root',
        'bgg_custom_dev.menu_bgg_appointment_tracking',
        'bgg_custom_dev.menu_bgg_commercial_dashboard',
        'bgg_custom_dev.menu_bgg_commercial_kpi',
    ]
    for xmlid in menu_xmlids:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.groups_id = [(4, admin_group.id)]

    _logger.info("Dashboard menus restricted to Admin group (ID: %s).", admin_group.id)
