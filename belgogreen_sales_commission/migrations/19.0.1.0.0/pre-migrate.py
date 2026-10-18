# -*- coding: utf-8 -*-
"""Move the commission plans off the Enterprise ``sale_commission`` module.

Up to 19.0.0.0 this module extended the Enterprise models
``sale.commission.plan`` and ``sale.commission.plan.user``. From 19.0.1.0.0 it
owns ``bgg.commission.plan`` and ``bgg.commission.plan.user`` instead, so it
keeps working once Enterprise is uninstalled (Community + OCA target).

This script runs before the module's models are loaded. It creates the new
tables and copies the plans and assignments into them WITH THEIR IDS, so every
existing ``plan_id`` (hr.commission.role.config, sale.commission) stays valid;
Odoo then repoints the foreign keys to the new tables when the module loads.

The copied Enterprise plans are then set to cancelled targets, so Enterprise
stops using them and no 'hierarchical' value is left in its ``type`` column.
Safe to run several times: rows already copied are skipped.
"""
import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)

OLD_PLAN = 'sale_commission_plan'
OLD_PLAN_USER = 'sale_commission_plan_user'
NEW_PLAN = 'bgg_commission_plan'
NEW_PLAN_USER = 'bgg_commission_plan_user'


def _text(columns, column):
    """SQL expression reading a Char column that may be translatable (jsonb)."""
    if columns[column]['udt_name'] == 'jsonb':
        return (f"COALESCE({column}->>'en_US', "
                f"(SELECT value FROM jsonb_each_text({column}) LIMIT 1))")
    return column


def _or(columns, column, default):
    """The column if the source table has it, else a constant default."""
    if column in columns:
        return f"COALESCE({column}, {default})" if default != 'NULL' else column
    return default


def _copy_plans(cr):
    cols = sql.table_columns(cr, OLD_PLAN)
    if not sql.table_exists(cr, NEW_PLAN):
        cr.execute(f"""
            CREATE TABLE {NEW_PLAN} (
                id SERIAL NOT NULL PRIMARY KEY,
                name VARCHAR,
                active BOOLEAN,
                company_id INTEGER,
                date_from DATE,
                date_to DATE,
                state VARCHAR,
                require_invoice_paid BOOLEAN,
                create_uid INTEGER,
                create_date TIMESTAMP,
                write_uid INTEGER,
                write_date TIMESTAMP
            )
        """)
    # Hierarchical plans, plus any other plan still referenced by our records
    # (copied as cancelled so it never generates commissions).
    referenced = ["SELECT plan_id FROM hr_commission_role_config"]
    if sql.column_exists(cr, 'sale_commission', 'plan_id'):
        referenced.append("SELECT plan_id FROM sale_commission WHERE plan_id IS NOT NULL")
    is_hier = "type = 'hierarchical'" if 'type' in cols else "TRUE"
    cr.execute(f"""
        INSERT INTO {NEW_PLAN} (id, name, active, company_id, date_from, date_to,
                                state, require_invoice_paid,
                                create_uid, create_date, write_uid, write_date)
        SELECT id, {_text(cols, 'name')}, {_or(cols, 'active', 'TRUE')}, company_id,
               {_or(cols, 'date_from', 'NULL')}, {_or(cols, 'date_to', 'NULL')},
               CASE WHEN {is_hier} THEN COALESCE(state, 'draft') ELSE 'cancel' END,
               {_or(cols, 'require_invoice_paid', 'TRUE')},
               create_uid, create_date, write_uid, write_date
          FROM {OLD_PLAN}
         WHERE {is_hier} OR id IN ({' UNION '.join(referenced)})
        ON CONFLICT (id) DO NOTHING
    """)
    copied = cr.rowcount
    cr.execute(f"""
        SELECT setval(pg_get_serial_sequence('{NEW_PLAN}', 'id'),
                      GREATEST((SELECT MAX(id) FROM {NEW_PLAN}), 1))
    """)
    return copied


def _copy_plan_users(cr):
    if not sql.table_exists(cr, OLD_PLAN_USER):
        return 0
    cols = sql.table_columns(cr, OLD_PLAN_USER)
    if not sql.table_exists(cr, NEW_PLAN_USER):
        cr.execute(f"""
            CREATE TABLE {NEW_PLAN_USER} (
                id SERIAL NOT NULL PRIMARY KEY,
                plan_id INTEGER,
                user_id INTEGER,
                date_from DATE,
                date_to DATE,
                role_id INTEGER,
                manager_id INTEGER,
                company_id INTEGER,
                role_sequence INTEGER,
                create_uid INTEGER,
                create_date TIMESTAMP,
                write_uid INTEGER,
                write_date TIMESTAMP
            )
        """)
    def col(name):
        return f'pu.{name}' if name in cols else 'NULL'

    # company_id and role_sequence are stored related fields: rebuilt from the
    # plan and the role rather than trusted from the old table.
    cr.execute(f"""
        INSERT INTO {NEW_PLAN_USER} (id, plan_id, user_id, date_from, date_to,
                                     role_id, manager_id, company_id, role_sequence,
                                     create_uid, create_date, write_uid, write_date)
        SELECT pu.id, pu.plan_id, pu.user_id,
               {col('date_from')}, {col('date_to')}, {col('role_id')}, {col('manager_id')},
               p.company_id, role.sequence,
               pu.create_uid, pu.create_date, pu.write_uid, pu.write_date
          FROM {OLD_PLAN_USER} pu
          JOIN {NEW_PLAN} p ON p.id = pu.plan_id
     LEFT JOIN sale_commission_role role ON role.id = {col('role_id')}
         WHERE pu.user_id IS NOT NULL
        ON CONFLICT (id) DO NOTHING
    """)
    copied = cr.rowcount
    cr.execute(f"""
        SELECT setval(pg_get_serial_sequence('{NEW_PLAN_USER}', 'id'),
                      GREATEST((SELECT MAX(id) FROM {NEW_PLAN_USER}), 1))
    """)
    return copied


def _move_chatter(cr):
    """Keep the plans' chatter (messages, followers, attachments)."""
    cr.execute("""
        UPDATE mail_message SET model = 'bgg.commission.plan'
         WHERE model = 'sale.commission.plan'
           AND res_id IN (SELECT id FROM bgg_commission_plan)
    """)
    cr.execute("""
        UPDATE mail_followers SET res_model = 'bgg.commission.plan'
         WHERE res_model = 'sale.commission.plan'
           AND res_id IN (SELECT id FROM bgg_commission_plan)
    """)
    cr.execute("""
        UPDATE ir_attachment SET res_model = 'bgg.commission.plan'
         WHERE res_model = 'sale.commission.plan'
           AND res_id IN (SELECT id FROM bgg_commission_plan)
    """)


def _retire_enterprise_plans(cr):
    """Stop Enterprise from using the plans that now live in our model."""
    if not sql.column_exists(cr, OLD_PLAN, 'type'):
        return
    cr.execute(f"""
        UPDATE {OLD_PLAN} SET type = 'target', state = 'cancel'
         WHERE type = 'hierarchical'
    """)


def migrate(cr, version):
    if not version or not sql.table_exists(cr, OLD_PLAN):
        return
    plans = _copy_plans(cr)
    users = _copy_plan_users(cr)
    _move_chatter(cr)
    _retire_enterprise_plans(cr)
    _logger.info(
        "belgogreen_sales_commission: copied %s commission plan(s) and %s plan "
        "assignment(s) from sale_commission to bgg.commission.plan[.user]",
        plans, users)
