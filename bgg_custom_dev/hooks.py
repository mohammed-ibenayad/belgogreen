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


def backfill_noshow_dates(env):
    """Stamp x_noshow_date for existing call-center no-shows that predate this
    feature, so they enter the recyclage workflow. Anchored on the missed
    appointment time (we have no record of when they were originally flagged).
    """
    events = env['calendar.event'].search([
        ('appointment_status', '=', 'no_show'),
        ('x_noshow_date', '=', False),
    ])
    count = 0
    for event in events:
        if event._is_call_center_appointment():
            event.with_context(skip_calendar_automation=True).write(
                {'x_noshow_date': event.stop or event.start})
            count += 1
    if count:
        _logger.info("BGG no-show workflow: backfilled x_noshow_date on %s "
                     "existing call-center no-shows.", count)


def link_external_groups(env):
    """Link the manually-created groups to module xmlids and gate the
    call-center recyclage menu/action by the 'Call Center' group.
    """
    imd = env['ir.model.data']
    resolved = {}

    for xmlid, name in EXTERNAL_GROUPS.items():
        # res.groups.name is translatable and may be cased differently per
        # language; resolve it robustly (this hook runs in the system language).
        group = env['calendar.event']._find_group_by_name(name)
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

    backfill_noshow_dates(env)

    # Restrict the recyclage queue (menu + action) to the Call Center group.
    # Odoo 19 renamed the "groups_id" field to "group_ids".
    call_center = resolved.get('group_call_center')
    if call_center:
        for ref in ('menu_bgg_noshow_recyclage_root',
                    'menu_bgg_noshow_recyclage_queue'):
            menu = env.ref('bgg_custom_dev.%s' % ref, raise_if_not_found=False)
            if menu:
                menu.group_ids = [(6, 0, [call_center.id])]
        action = env.ref('bgg_custom_dev.action_noshow_recyclage_queue',
                         raise_if_not_found=False)
        if action:
            action.group_ids = [(6, 0, [call_center.id])]
