# -*- coding: utf-8 -*-
"""bgg_custom_dev no longer depends on Odoo Enterprise (19.0.2.0.0).

Its business rules now read its own fields instead of the Enterprise ones:

    appointment.type                      -> bgg.rdv.type (same ids)
    calendar.event.appointment_type_id    -> x_rdv_type_id
    calendar.event.appointment_status     -> x_rdv_status
    appointment.answer.input (per event)  -> x_rdv_answers (text summary)
    project.project.is_fsm                -> x_is_sss_project

This script runs before the module loads. It creates those columns and fills
them from the Enterprise data in SQL (one statement per table, no ORM
recompute), and hands the xmlids of what the module defined on Enterprise
models (appointment.type.x_appointment_ref) over to the new bridge module
bgg_custom_dev_ee, so they are not deleted by this update. The post-migration
installs that bridge, which keeps both sides in sync until Enterprise goes.

Safe to run several times; does nothing for a table/column that is missing.
"""
import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)

BRIDGE = 'bgg_custom_dev_ee'


def _text(cr, table, column, alias):
    """SQL expression reading a Char that may be translatable (jsonb)."""
    expr = f'{alias}.{column}'
    if sql.table_columns(cr, table)[column]['udt_name'] == 'jsonb':
        return (f"COALESCE({expr}->>'fr_BE', {expr}->>'en_US', "
                f"(SELECT value FROM jsonb_each_text({expr}) LIMIT 1))")
    return expr


def _add_column(cr, table, column, coltype):
    if not sql.column_exists(cr, table, column):
        sql.create_column(cr, table, column, coltype)


def _copy_rdv_types(cr):
    if not sql.table_exists(cr, 'bgg_rdv_type'):
        cr.execute("""
            CREATE TABLE bgg_rdv_type (
                id SERIAL NOT NULL PRIMARY KEY,
                name VARCHAR, code VARCHAR, sequence INTEGER, active BOOLEAN,
                create_uid INTEGER, create_date TIMESTAMP,
                write_uid INTEGER, write_date TIMESTAMP)
        """)
    if not sql.table_exists(cr, 'appointment_type'):
        return 0
    cols = sql.table_columns(cr, 'appointment_type')
    code = 'apt.x_appointment_ref' if 'x_appointment_ref' in cols else 'NULL'
    seq = 'COALESCE(apt.sequence, 10)' if 'sequence' in cols else '10'
    active = 'COALESCE(apt.active, TRUE)' if 'active' in cols else 'TRUE'
    cr.execute(f"""
        INSERT INTO bgg_rdv_type (id, name, code, sequence, active,
                                  create_uid, create_date, write_uid, write_date)
        SELECT apt.id, {_text(cr, 'appointment_type', 'name', 'apt')}, NULLIF({code}, ''),
               {seq}, {active}, apt.create_uid, apt.create_date, apt.write_uid, apt.write_date
          FROM appointment_type apt
        ON CONFLICT (id) DO NOTHING
    """)
    copied = cr.rowcount
    cr.execute("""
        SELECT setval(pg_get_serial_sequence('bgg_rdv_type', 'id'),
                      GREATEST((SELECT MAX(id) FROM bgg_rdv_type), 1))
    """)
    # Link each appointment type to its RDV type (bridge field).
    _add_column(cr, 'appointment_type', 'x_rdv_type_id', 'int4')
    cr.execute("""
        UPDATE appointment_type apt SET x_rdv_type_id = apt.id
         WHERE apt.x_rdv_type_id IS NULL
           AND EXISTS (SELECT 1 FROM bgg_rdv_type t WHERE t.id = apt.id)
    """)
    return copied


def _copy_event_fields(cr):
    _add_column(cr, 'calendar_event', 'x_rdv_type_id', 'int4')
    _add_column(cr, 'calendar_event', 'x_rdv_status', 'varchar')
    _add_column(cr, 'calendar_event', 'x_rdv_answers', 'text')
    events = 0
    if sql.column_exists(cr, 'calendar_event', 'appointment_type_id'):
        cr.execute("""
            UPDATE calendar_event ce
               SET x_rdv_type_id = ce.appointment_type_id
             WHERE ce.x_rdv_type_id IS NULL AND ce.appointment_type_id IS NOT NULL
               AND EXISTS (SELECT 1 FROM bgg_rdv_type t WHERE t.id = ce.appointment_type_id)
        """)
        events = cr.rowcount
    if sql.column_exists(cr, 'calendar_event', 'appointment_status'):
        cr.execute("""
            UPDATE calendar_event
               SET x_rdv_status = appointment_status
             WHERE x_rdv_status IS NULL
               AND appointment_status IN ('request', 'booked', 'attended', 'no_show', 'cancelled')
        """)
    answers = 0
    if all(sql.table_exists(cr, t) for t in ('appointment_answer_input', 'appointment_question')):
        q_name = _text(cr, 'appointment_question', 'name', 'q')
        q_seq = 'q.sequence' if sql.column_exists(cr, 'appointment_question', 'sequence') else '0'
        if sql.table_exists(cr, 'appointment_answer'):
            ans_join = 'LEFT JOIN appointment_answer an ON an.id = ai.value_answer_id'
            ans_name = _text(cr, 'appointment_answer', 'name', 'an')
        else:
            ans_join, ans_name = '', 'NULL'
        value = f"COALESCE(NULLIF(ai.value_text_box, ''), {ans_name})"
        cr.execute(f"""
            UPDATE calendar_event ce SET x_rdv_answers = sub.summary
              FROM (SELECT ai.calendar_event_id,
                           string_agg({q_name} || ' : ' || {value}, E'\\n'
                                      ORDER BY {q_seq}, q.id, ai.id) AS summary
                      FROM appointment_answer_input ai
                      JOIN appointment_question q ON q.id = ai.question_id
                      {ans_join}
                     WHERE ai.calendar_event_id IS NOT NULL
                       AND {value} IS NOT NULL
                  GROUP BY ai.calendar_event_id) sub
             WHERE ce.id = sub.calendar_event_id AND ce.x_rdv_answers IS NULL
        """)
        answers = cr.rowcount
    return events, answers


def _copy_sss_flag(cr):
    _add_column(cr, 'project_project', 'x_is_sss_project', 'bool')
    if not sql.column_exists(cr, 'project_project', 'is_fsm'):
        return 0
    cr.execute("""
        UPDATE project_project SET x_is_sss_project = TRUE
         WHERE is_fsm AND x_is_sss_project IS NOT TRUE
    """)
    return cr.rowcount


def _hand_over_to_bridge(cr):
    """The model/field definitions bgg_custom_dev made on Enterprise models now
    live in the bridge: move their xmlids so this update does not delete them."""
    cr.execute(f"""
        UPDATE ir_model_data d SET module = %s
         WHERE d.module = 'bgg_custom_dev'
           AND (d.name LIKE 'model\\_appointment\\_%%' OR d.name LIKE 'field\\_appointment\\_%%')
           AND NOT EXISTS (SELECT 1 FROM ir_model_data o
                            WHERE o.module = %s AND o.name = d.name)
    """, [BRIDGE, BRIDGE])
    return cr.rowcount


def migrate(cr, version):
    if not version:
        return
    types = _copy_rdv_types(cr)
    events, answers = _copy_event_fields(cr)
    sss = _copy_sss_flag(cr)
    xmlids = _hand_over_to_bridge(cr)
    _logger.info(
        "bgg_custom_dev: copied %s RDV type(s), RDV type/status on %s event(s), "
        "questionnaire answers on %s event(s), SSS flag on %s project(s); "
        "%s xmlid(s) handed over to %s", types, events, answers, sss, xmlids, BRIDGE)
