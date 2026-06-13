# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID
from odoo.addons.bgg_custom_dev.hooks import link_external_groups


def migrate(cr, version):
    """On upgrade, link the manually-created 'Commercial'/'Call Center' groups
    and gate the recyclage menu (post_init_hook only runs on fresh install).
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    link_external_groups(env)
