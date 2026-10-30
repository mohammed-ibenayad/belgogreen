# -*- coding: utf-8 -*-
"""Reload the commission invoice-request email template.

It was written in the old Mako syntax (``${...}``, ``% if``), which Odoo 19
prints as-is. The record is noupdate, so a normal module update skips it:
reload its data file once in 'init' mode to rewrite it in Odoo 19 syntax.
"""
from odoo import api, SUPERUSER_ID
from odoo.tools.convert import convert_file


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    convert_file(env, 'belgogreen_sales_commission', 'data/email_template_data.xml',
                 idref={}, mode='init', noupdate=True)
