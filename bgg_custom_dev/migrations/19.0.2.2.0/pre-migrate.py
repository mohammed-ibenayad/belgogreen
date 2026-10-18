# -*- coding: utf-8 -*-
"""Commercials per RDV type (19.0.2.2.0).

Copies the staff users of each Enterprise appointment type to its RDV type
(bgg.rdv.type.user_ids, same ids as the appointment types), before the
Enterprise tables go. The bridge bgg_custom_dev_ee keeps them in sync
afterwards. Safe to run several times.
"""
import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""CREATE TABLE IF NOT EXISTS bgg_rdv_type_res_users_rel (
                      rdv_type_id INTEGER NOT NULL REFERENCES bgg_rdv_type(id) ON DELETE CASCADE,
                      user_id INTEGER NOT NULL REFERENCES res_users(id) ON DELETE CASCADE,
                      PRIMARY KEY (rdv_type_id, user_id))""")
    cr.execute("""SELECT relation_table, column1, column2 FROM ir_model_fields
                  WHERE model = 'appointment.type' AND name = 'staff_user_ids'""")
    row = cr.fetchone()
    if not row or not all(row) or not sql.table_exists(cr, row[0]):
        return
    table, type_col, user_col = row
    cr.execute(f"""
        INSERT INTO bgg_rdv_type_res_users_rel (rdv_type_id, user_id)
        SELECT DISTINCT apt.x_rdv_type_id, rel."{user_col}"
          FROM "{table}" rel
          JOIN appointment_type apt ON apt.id = rel."{type_col}"
          JOIN res_users u ON u.id = rel."{user_col}"
         WHERE apt.x_rdv_type_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    _logger.info("bgg_custom_dev: %s commercial(s) copied to the RDV types from the appointment types", cr.rowcount)
