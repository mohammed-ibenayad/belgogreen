# -*- coding: utf-8 -*-
"""Sellable products list (19.0.2.3.0).

The Studio change of 2026-10-21 on the sellable products list ("Created by"
and "Created on" columns, category always shown) is now a module view. Its
Studio view is switched off, otherwise both would apply while Studio is
still installed. Safe to run several times.
"""
import logging

_logger = logging.getLogger(__name__)

STUDIO_VIEWS = [
    'odoo_studio_product__a3fb1edc-dc69-4018-aa5d-8678e1ee7f4d',  # sellable products list
]


def migrate(cr, version):
    if not version:
        return
    cr.execute("""UPDATE ir_ui_view SET active = false
                  WHERE active AND id IN (SELECT res_id FROM ir_model_data
                                          WHERE module = 'studio_customization' AND model = 'ir.ui.view'
                                            AND name IN %s)""",
               [tuple(STUDIO_VIEWS)])
    if cr.rowcount:
        _logger.info("bgg_custom_dev: %s Studio view(s) switched off (rebuilt in the module)", cr.rowcount)
