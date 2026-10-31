# -*- coding: utf-8 -*-
"""AMSS ADMIN books the call-centre types (19.0.1.5.0), as the install hook
does now."""

from odoo import SUPERUSER_ID, api

from odoo.addons.bgg_booking.hooks import give_amss_admin_booking


def migrate(cr, version):
    give_amss_admin_booking(api.Environment(cr, SUPERUSER_ID, {}))
