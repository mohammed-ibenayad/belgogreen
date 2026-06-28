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
    """Link the manually-created 'Commercial'/'Call Center' groups to module
    xmlids (resolved by name) and backfill the no-show anchor on existing
    call-center no-shows.
    """
    imd = env['ir.model.data']

    for xmlid, name in EXTERNAL_GROUPS.items():
        # res.groups.name is translatable and may be cased differently per
        # language; resolve it robustly (this hook runs in the system language).
        group = env['calendar.event']._find_group_by_name(name)
        if not group:
            _logger.warning(
                "BGG no-show workflow: group '%s' not found; xmlid link skipped. "
                "Create the group or assign it manually.", name)
            continue

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
