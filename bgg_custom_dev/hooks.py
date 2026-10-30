# -*- coding: utf-8 -*-

import logging

from odoo import Command

_logger = logging.getLogger(__name__)

# The "Commercial" and "Call Center" roles were created manually outside the
# custom modules. They are declared in security/groups.xml since 19.0.2.3.0
# (existing groups adopted); this hook still resolves them by name (same
# pattern as sale_order.py and avis_count_report.py) and maps them to the
# module xmlids, for databases where the adoption did not run.
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
        ('x_rdv_status', '=', 'no_show'),
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


# --- Stages of the SSS projects (migrations 19.0.2.3.0 and 19.0.2.3.1) ---

# French and older English names of the SSS stages (see sale_order_sss.SSS_STAGES)
SSS_STAGE_NAMES = ('SSS: À faire', 'FSM: ToDo', 'SSS: Encours/Fait', 'FSM: In progress/Done')
SSS_TODO_NAMES = ('SSS: À faire', 'FSM: ToDo')
NEW_STAGE_NAME = 'Nouveau'

_HAS_NAME = "EXISTS (SELECT 1 FROM jsonb_each_text(%s.name) WHERE value IN %%s)"


def clean_sss_stages(cr):
    """Tasks of a "Nouveau" stage of an SSS project go to its "SSS: À faire";
    the other stages are taken off the SSS projects when no SSS task is in
    them, and deleted when nothing uses them. In SQL (no automation, no
    stage-change date). See migration 19.0.2.3.0."""
    sss = "SELECT id FROM project_project WHERE x_is_sss_project"

    # tasks of a "Nouveau" stage -> "SSS: À faire" of their project
    todo = """SELECT t.id FROM project_task_type t
                JOIN project_task_type_rel r ON r.type_id = t.id AND r.project_id = k.project_id
               WHERE %s ORDER BY t.sequence, t.id LIMIT 1""" % (_HAS_NAME % 't')
    cr.execute("""
        UPDATE project_task k SET stage_id = (%s)
         WHERE k.project_id IN (%s)
           AND k.stage_id IN (SELECT s.id FROM project_task_type s WHERE %s)
           AND EXISTS (%s)
    """ % (todo, sss, _HAS_NAME % 's', todo), [SSS_TODO_NAMES, (NEW_STAGE_NAME,), SSS_TODO_NAMES])
    if cr.rowcount:
        _logger.info("bgg_custom_dev: %s SSS task(s) moved from a 'Nouveau' stage to 'SSS: À faire'", cr.rowcount)

    # other stages off the SSS projects, when no SSS task is in them
    cr.execute("""
        DELETE FROM project_task_type_rel r
         USING project_task_type t
         WHERE t.id = r.type_id AND r.project_id IN (%s) AND NOT %s
           AND NOT EXISTS (SELECT 1 FROM project_task k WHERE k.stage_id = t.id AND k.project_id IN (%s))
           -- the project keeps its own SSS stages
           AND EXISTS (SELECT 1 FROM project_task_type_rel r2 JOIN project_task_type t2 ON t2.id = r2.type_id
                        WHERE r2.project_id = r.project_id AND %s)
        RETURNING r.type_id
    """ % (sss, _HAS_NAME % 't', sss, _HAS_NAME % 't2'), [SSS_STAGE_NAMES, SSS_STAGE_NAMES])
    stage_ids = sorted({row[0] for row in cr.fetchall()})
    if stage_ids:
        _logger.info("bgg_custom_dev: %s stage(s) taken off the SSS projects: %s", len(stage_ids), stage_ids)
        # deleted when nothing uses them any more (not a personal stage)
        cr.execute("""
            DELETE FROM project_task_type t
             WHERE t.id IN %s AND t.user_id IS NULL
               AND NOT EXISTS (SELECT 1 FROM project_task_type_rel r WHERE r.type_id = t.id)
               AND NOT EXISTS (SELECT 1 FROM project_task k WHERE k.stage_id = t.id)
            RETURNING t.id
        """, [tuple(stage_ids)])
        deleted = [row[0] for row in cr.fetchall()]
        if deleted:
            _logger.info("bgg_custom_dev: %s unused stage(s) deleted: %s", len(deleted), deleted)

    # left: stages other than the SSS ones still holding SSS tasks
    cr.execute("""
        SELECT t.id, COALESCE(t.name->>'fr_BE', t.name->>'en_US'), count(k.id)
          FROM project_task_type t JOIN project_task k ON k.stage_id = t.id
         WHERE k.project_id IN (%s) AND NOT %s
         GROUP BY t.id ORDER BY t.id
    """ % (sss, _HAS_NAME % 't'), [SSS_STAGE_NAMES])
    for stage_id, name, count in cr.fetchall():
        _logger.warning("bgg_custom_dev: stage %r (id %s) still holds %s SSS task(s), left as is",
                        name, stage_id, count)


def ensure_sss_stages(env):
    """Give the SSS projects that miss them their two SSS stages, as
    "Créer tâches SSS" does (the older projects, made in Field Service, only
    had the stages added there)."""
    from .models.sale_order_sss import SSS_STAGES
    cr = env.cr
    vals = []
    for sequence, names in enumerate(SSS_STAGES, start=1):
        cr.execute("""
            SELECT p.id FROM project_project p
             WHERE p.x_is_sss_project
               AND NOT EXISTS (SELECT 1 FROM project_task_type_rel r JOIN project_task_type t ON t.id = r.type_id
                                WHERE r.project_id = p.id AND %s)
             ORDER BY p.id
        """ % (_HAS_NAME % 't'), [tuple(names)])
        vals += [{'name': names[0], 'sequence': sequence, 'fold': False, 'project_ids': [Command.link(project_id)]}
                 for (project_id,) in cr.fetchall()]
    if vals:
        env['project.task.type'].create(vals)
        _logger.info("bgg_custom_dev: %s SSS stage(s) created on the SSS projects that missed them", len(vals))


def fix_sss_stages(env):
    ensure_sss_stages(env)
    clean_sss_stages(env.cr)
