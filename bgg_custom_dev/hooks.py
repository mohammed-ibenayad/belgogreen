# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)

# The "Commercial" and "Call Center" roles were created manually outside the
# custom modules and never transferred into them, so they have no xmlid. We
# resolve them by name (same pattern already used in sale_order.py and
# avis_count_report.py) and map them to module xmlids for reuse.
EXTERNAL_GROUPS = {
    'group_commercial': 'Commercial',
    'group_call_center': 'Call Center',
}


def link_external_groups(env):
    """Link the manually-created groups to module xmlids and gate the
    call-center recyclage menu/action by the 'Call Center' group.
    """
    imd = env['ir.model.data']
    resolved = {}

    for xmlid, name in EXTERNAL_GROUPS.items():
        group = env['res.groups'].search([('name', '=', name)], limit=1)
        if not group:
            _logger.warning(
                "BGG no-show workflow: group '%s' not found; menu gating and "
                "xmlid link skipped. Create the group or assign it manually.",
                name)
            continue
        resolved[xmlid] = group

        record = imd.search([
            ('module', '=', 'bgg_custom_dev'),
            ('name', '=', xmlid),
        ], limit=1)
        if record:
            record.res_id = group.id
        else:
            imd.create({
                'module': 'bgg_custom_dev',
                'name': xmlid,
                'model': 'res.groups',
                'res_id': group.id,
                'noupdate': True,
            })

    # Restrict the recyclage queue (menu + action) to the Call Center group.
    call_center = resolved.get('group_call_center')
    if call_center:
        for ref in ('menu_bgg_noshow_recyclage_root',
                    'menu_bgg_noshow_recyclage_queue'):
            menu = env.ref('bgg_custom_dev.%s' % ref, raise_if_not_found=False)
            if menu:
                menu.groups_id = [(6, 0, [call_center.id])]
        action = env.ref('bgg_custom_dev.action_noshow_recyclage_queue',
                         raise_if_not_found=False)
        if action:
            action.groups_id = [(6, 0, [call_center.id])]
