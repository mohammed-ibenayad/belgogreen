# -*- coding: utf-8 -*-

from . import models
from . import report
from . import controllers

import logging
_logger = logging.getLogger(__name__)


def _assign_admin_group_to_menus(env):
    """Restrict dashboard menus: Suivi Commercial to Admin, Avis pivot to Admin + Call Center.

    Parent menus have no group restriction so they auto-show when any child is visible.
    """
    admin_group = env['res.groups'].search([('name', '=', 'Admin')], limit=1)
    call_center_group = env['res.groups'].search([('name', '=', 'Call Center')], limit=1)

    if not admin_group:
        _logger.warning("No 'Admin' group found. Dashboard menus will remain unrestricted.")
        return

    # Parent menus: clear any existing group restriction so visibility follows from children
    for xmlid in ['bgg_custom_dev.menu_bgg_custom_dev_root', 'bgg_custom_dev.menu_bgg_appointment_tracking']:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.group_ids = [(5,)]

    # Suivi Commercial: Admin only
    menu = env.ref('bgg_custom_dev.menu_bgg_commercial_dashboard', raise_if_not_found=False)
    if menu:
        menu.group_ids = [(6, 0, [admin_group.id])]

    # Avis pivot: Admin + Call Center
    menu = env.ref('bgg_custom_dev.menu_bgg_avis_count', raise_if_not_found=False)
    if menu:
        group_ids = [admin_group.id]
        if call_center_group:
            group_ids.append(call_center_group.id)
        else:
            _logger.warning("No 'Call Center' group found. Avis pivot restricted to Admin only.")
        menu.group_ids = [(6, 0, group_ids)]

    _logger.info("Dashboard menus: Suivi Commercial -> Admin (ID: %s), Avis pivot -> Admin + Call Center.", admin_group.id)
