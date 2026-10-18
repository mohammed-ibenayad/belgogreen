# -*- coding: utf-8 -*-
"""After the Studio customizations moved into the module (19.0.2.1.0):

- the Studio server actions now ported to the module are taken out of the
  Action menu (unbound, not deleted), so each appears once;
- the Studio compute code left on the "Tâches" counter field is cleared;
- the saved filters on calendar events and projects / tasks are repointed
  from the Enterprise fields to the module's own ones (same values), so they
  keep working once Enterprise is removed:
      calendar.event  appointment_type_id -> x_rdv_type_id
                      appointment_status  -> x_rdv_status
      project.task    is_fsm              -> project_id.x_is_sss_project
      project.project is_fsm              -> x_is_sss_project
"""
import logging
import re

_logger = logging.getLogger(__name__)

# Studio actions replaced by bgg_custom_dev actions or rules
PORTED_STUDIO_ACTIONS = (
    '(CA) Create FSM Project and Tasks',
    '(CA) Rappel pour statuer les rendez-vous énergétique',
    'Clôturer les projets Admin/SSS',
    'Recalculate Project deadline',
    '(CA) Detect Commercial',  # x_studio_commercial is computed by the module
)

_NAME = r'(?<![\w.])%s(?!\w)'
FILTER_REPLACEMENTS = {
    'calendar.event': [
        (_NAME % r'appointment_type_id\.x_appointment_ref', 'x_rdv_type_id.code'),
        (_NAME % 'appointment_type_id', 'x_rdv_type_id'),
        (_NAME % 'appointment_status', 'x_rdv_status'),
    ],
    'project.task': [
        (r'(?<![\w.])project_id\.is_fsm(?!\w)', 'project_id.x_is_sss_project'),
        (_NAME % 'is_fsm', 'project_id.x_is_sss_project'),
    ],
    'project.project': [
        (_NAME % 'is_fsm', 'x_is_sss_project'),
    ],
}


def _unbind_ported_actions(cr):
    cr.execute("""
        UPDATE ir_act_server a SET binding_model_id = NULL
         WHERE a.binding_model_id IS NOT NULL
           AND EXISTS (SELECT 1 FROM jsonb_each_text(a.name) WHERE value IN %s)
           AND NOT EXISTS (SELECT 1 FROM ir_model_data d
                            WHERE d.model = 'ir.actions.server' AND d.res_id = a.id
                              AND d.module NOT IN ('studio_customization', '__custom__', '__export__'))
    """, [PORTED_STUDIO_ACTIONS])
    if cr.rowcount:
        _logger.info("bgg_custom_dev: %s Studio action(s) removed from the Action menu (now in the module)",
                     cr.rowcount)


def _repoint_filters(cr):
    changed = 0
    for model, replacements in FILTER_REPLACEMENTS.items():
        cr.execute("SELECT id, domain, context, sort FROM ir_filters WHERE model_id = %s", [model])
        for filter_id, *values in cr.fetchall():
            new_values = []
            for value in values:
                for pattern, replacement in replacements:
                    value = re.sub(pattern, replacement, value) if value else value
                new_values.append(value)
            if new_values != values:
                cr.execute("UPDATE ir_filters SET domain = %s, context = %s, sort = %s WHERE id = %s",
                           [*new_values, filter_id])
                changed += 1
    if changed:
        _logger.info("bgg_custom_dev: %s saved filter(s) repointed to the module's own fields", changed)


def _clear_studio_compute(cr):
    # Studio stored its compute code on the field; the module computes it now.
    cr.execute("""UPDATE ir_model_fields SET compute = NULL, depends = NULL
                  WHERE model = 'sale.order' AND name = 'x_sale_order_id_project_task_count'
                    AND state = 'base' AND compute IS NOT NULL""")


def migrate(cr, version):
    if not version:
        return
    _clear_studio_compute(cr)
    _unbind_ported_actions(cr)
    _repoint_filters(cr)
