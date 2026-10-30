# -*- coding: utf-8 -*-
"""Stages added by mistake to the SSS projects (19.0.2.3.0).

An SSS project has two stages, "SSS: À faire" and "SSS: Encours/Fait".
Columns added by hand in the Field Service kanban created more stages
("Nouveau", and "Planifié", "En cours", "Terminé", "Annulé"), linked to
every SSS project, so each SSS task showed eight "Nouveau" stages. This
script:

- moves the SSS tasks of a "Nouveau" stage to the "SSS: À faire" stage of
  their project (a new task, not started);
- takes the other stages off the SSS projects when no SSS task is in them;
- deletes those stages when no project and no task use them any more.

A stage still holding SSS tasks (other than "Nouveau") is left and logged.
In SQL, so no automation or stage-change date is triggered. Safe to run
several times.
"""
import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)

# French and older English names of the SSS stages (see sale_order_sss.SSS_STAGES)
SSS_STAGE_NAMES = ('SSS: À faire', 'FSM: ToDo', 'SSS: Encours/Fait', 'FSM: In progress/Done')
SSS_TODO_NAMES = ('SSS: À faire', 'FSM: ToDo')
NEW_STAGE_NAME = 'Nouveau'

_HAS_NAME = "EXISTS (SELECT 1 FROM jsonb_each_text(%s.name) WHERE value IN %%s)"


def migrate(cr, version):
    if not version or not sql.column_exists(cr, 'project_project', 'x_is_sss_project'):
        return
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
