# -*- coding: utf-8 -*-
"""Activity access rules made by hand (19.0.2.3.2).

The two "[ADD]" rules on activities (production rules 249 and 250) get the
xmlids of security/activity_rules.xml, so they are adopted, not created
twice; their condition is kept as it is. Safe to run several times.
"""
from odoo.addons.bgg_custom_dev.hooks import adopt_rules

HAND_MADE_RULES = {
    'rule_mail_activity_own_or_assigned': ('[ADD] Manage Own Activities or Assigned to Others', None),
    'rule_mail_activity_administrators_all': ('[ADD] Administrators can access all activities.', None),
}


def migrate(cr, version):
    if not version:
        return
    adopt_rules(cr, HAND_MADE_RULES)
