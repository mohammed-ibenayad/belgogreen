# -*- coding: utf-8 -*-
"""The Odoo Studio customizations move into this module (19.0.2.1.0).

The module now declares the Studio fields under the same names (data kept),
rebuilds the Studio views and ports the Studio server actions. Before the
module loads, this script:

- gives the Studio group "AMSS ADMIN" (__custom__.group_58) the xmlid
  bgg_custom_dev.group_amss_admin, so it is adopted, not created twice;
- switches off the Studio views rebuilt by the module (otherwise both would
  apply, and some new views could not find what Studio already removed);
- detaches the saved filters made in Studio from studio_customization, so
  they are not deleted with Studio;
- links each SSS project to its sale order (x_sss_sale_order_id): from the
  order of its tasks, else from its name "<order> - SSS - <client>".

Safe to run several times.
"""
import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)

STUDIO = 'studio_customization'

# Studio views rebuilt by bgg_custom_dev / bgg_custom_dev_ee. The Studio
# changes of the "all tasks" and Field Service task lists (timesheet columns,
# Enterprise only) stay in Studio until it is removed.
STUDIO_VIEWS = [
    'odoo_studio_calendar_424ce40a-5926-4fa3-900b-5c6d6552b64a',  # calendar list
    'odoo_studio_calendar_19b64d69-b20b-473b-a264-a981d2c00203',  # calendar form
    'odoo_studio_ir_loggi_65d46727-c2a2-47ea-9bfc-a48e6bf07ec3',  # logs list
    'odoo_studio_appointm_27dca6d9-3fc0-4f16-886c-33be92624d25',  # appointment type form
    'odoo_studio_sale_ord_af45219c-97f2-4c46-bfb3-42d8634d47de',  # sale order form
    'odoo_studio_sale_ord_483ab422-4165-4634-bb3e-a19dd2a76d44',  # quotations list
    'odoo_studio_sale_ord_0b3930c8-93ad-4d90-90f3-829f79a7949d',  # sales list (upload)
    'odoo_studio_res_part_30bd288e-a891-4aca-93c9-3bce356853c4',  # contact form
    'odoo_studio_res_part_7ef14efb-f573-4236-894e-bf440be54892',  # contacts list
    'odoo_studio_sms_sms__41e31685-f7a6-4a3a-ba9b-8f1dba6e1c6a',  # SMS list
    'odoo_studio_project__e683f61e-d101-4169-8204-b5ad9a26f678',  # projects list
    'odoo_studio_account__7b0c3e3d-14fd-4339-8e74-6cd0b91372d0',  # payment term form
]


def _adopt_amss_admin_group(cr):
    cr.execute("SELECT 1 FROM ir_model_data WHERE module = 'bgg_custom_dev' AND name = 'group_amss_admin'")
    if cr.fetchone():
        return
    cr.execute("SELECT res_id FROM ir_model_data WHERE module = '__custom__' AND name = 'group_58' "
               "AND model = 'res.groups'")
    row = cr.fetchone()
    if not row:
        cr.execute("""SELECT id FROM res_groups
                      WHERE EXISTS (SELECT 1 FROM jsonb_each_text(name) WHERE value = 'AMSS ADMIN')
                      ORDER BY id LIMIT 1""")
        row = cr.fetchone()
    if not row:
        return
    cr.execute("""INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                  VALUES ('bgg_custom_dev', 'group_amss_admin', 'res.groups', %s, true)""", row)
    _logger.info("bgg_custom_dev: Studio group AMSS ADMIN (id %s) adopted as group_amss_admin", row[0])


def _deactivate_studio_views(cr):
    cr.execute("""UPDATE ir_ui_view SET active = false
                  WHERE active AND id IN (SELECT res_id FROM ir_model_data
                                          WHERE module = %s AND model = 'ir.ui.view' AND name IN %s)""",
               [STUDIO, tuple(STUDIO_VIEWS)])
    if cr.rowcount:
        _logger.info("bgg_custom_dev: %s Studio view(s) switched off (rebuilt in the module)", cr.rowcount)


def _detach_studio_filters(cr):
    cr.execute("DELETE FROM ir_model_data WHERE module = %s AND model = 'ir.filters'", [STUDIO])
    if cr.rowcount:
        _logger.info("bgg_custom_dev: %s saved filter(s) detached from Studio", cr.rowcount)


def _link_sss_projects(cr):
    if not sql.column_exists(cr, 'project_project', 'x_is_sss_project'):
        return
    if not sql.column_exists(cr, 'project_project', 'x_sss_sale_order_id'):
        sql.create_column(cr, 'project_project', 'x_sss_sale_order_id', 'int4')
    linked = 0
    if sql.column_exists(cr, 'project_task', 'sale_order_id'):
        cr.execute("""
            UPDATE project_project p SET x_sss_sale_order_id = t.order_id
              FROM (SELECT DISTINCT ON (project_id) project_id, sale_order_id AS order_id
                      FROM project_task
                     WHERE sale_order_id IS NOT NULL AND project_id IS NOT NULL
                     GROUP BY project_id, sale_order_id
                     ORDER BY project_id, count(*) DESC, sale_order_id) t
             WHERE p.id = t.project_id AND p.x_is_sss_project AND p.x_sss_sale_order_id IS NULL
        """)
        linked += cr.rowcount
    cr.execute("""
        UPDATE project_project p SET x_sss_sale_order_id = so.id
          FROM sale_order so
         WHERE p.x_is_sss_project AND p.x_sss_sale_order_id IS NULL
           AND split_part(COALESCE(p.name->>'en_US', p.name->>'fr_BE'), ' - SSS - ', 1) = so.name
    """)
    linked += cr.rowcount
    _logger.info("bgg_custom_dev: %s SSS project(s) linked to their sale order", linked)


def migrate(cr, version):
    if not version:
        return
    _adopt_amss_admin_group(cr)
    _deactivate_studio_views(cr)
    _detach_studio_filters(cr)
    _link_sss_projects(cr)
