# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Re-apply Admin group restriction to dashboard menus on upgrade."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    from bgg_custom_dev import _assign_admin_group_to_menus
    _assign_admin_group_to_menus(env)
