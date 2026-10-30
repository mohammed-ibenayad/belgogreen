# -*- coding: utf-8 -*-
"""Sellable products list and roles made by hand (19.0.2.3.0).

Before the module loads, this script:

- switches off the Studio view of the sellable products list (Studio
  change of 2026-10-21: "Created by" and "Created on" columns, category
  always shown), now a module view; otherwise both would apply while
  Studio is still installed;
- gives the roles created by hand in Odoo or in Studio the xmlids of the
  module's groups (security/groups.xml), so the existing groups are
  adopted with their members, not created twice.

Safe to run several times.
"""
import logging

_logger = logging.getLogger(__name__)

STUDIO_VIEWS = [
    'odoo_studio_product__a3fb1edc-dc69-4018-aa5d-8678e1ee7f4d',  # sellable products list
]

# module xmlid: (Studio xmlid or None, name of the group in any language)
HAND_MADE_GROUPS = {
    'group_commercial': (None, 'Commercial'),
    'group_call_center': (None, 'Call Center'),
    'group_administrateur': ('group_57', 'Administrateur'),
    'group_directeur_commercial': (None, 'Directeur Commercial'),
    'group_responsable_equipe_commercial': (None, 'Responsable Equipe Commercial'),
    'group_technicien': (None, 'Technicien'),
}


def _deactivate_studio_views(cr):
    cr.execute("""UPDATE ir_ui_view SET active = false
                  WHERE active AND id IN (SELECT res_id FROM ir_model_data
                                          WHERE module = 'studio_customization' AND model = 'ir.ui.view'
                                            AND name IN %s)""",
               [tuple(STUDIO_VIEWS)])
    if cr.rowcount:
        _logger.info("bgg_custom_dev: %s Studio view(s) switched off (rebuilt in the module)", cr.rowcount)


def _adopt_groups(cr):
    for xmlid, (custom_xmlid, name) in HAND_MADE_GROUPS.items():
        cr.execute("SELECT 1 FROM ir_model_data WHERE module = 'bgg_custom_dev' AND name = %s", [xmlid])
        if cr.fetchone():
            continue
        row = None
        if custom_xmlid:
            cr.execute("SELECT res_id FROM ir_model_data WHERE module = '__custom__' AND name = %s "
                       "AND model = 'res.groups'", [custom_xmlid])
            row = cr.fetchone()
        if not row:
            # only a group made by hand: a module's group of the same name
            # (e.g. an app's "Administrateur") is not taken
            cr.execute("""SELECT g.id FROM res_groups g
                          WHERE EXISTS (SELECT 1 FROM jsonb_each_text(g.name) WHERE lower(value) = lower(%s))
                            AND NOT EXISTS (SELECT 1 FROM ir_model_data d
                                             WHERE d.model = 'res.groups' AND d.res_id = g.id
                                               AND d.module NOT IN ('__custom__', '__export__'))
                          ORDER BY g.id LIMIT 1""", [name])
            row = cr.fetchone()
        if not row:
            continue
        cr.execute("""INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                      VALUES ('bgg_custom_dev', %s, 'res.groups', %s, true)""", [xmlid, row[0]])
        _logger.info("bgg_custom_dev: group %r (id %s) adopted as %s", name, row[0], xmlid)


def migrate(cr, version):
    if not version:
        return
    _deactivate_studio_views(cr)
    _adopt_groups(cr)
