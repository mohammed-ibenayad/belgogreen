# -*- coding: utf-8 -*-
"""Booking types, their calendar and the commercials' resources shared by all
companies (they were created in the company of the user who installed)."""

from odoo import SUPERUSER_ID, api

from odoo.addons.bgg_booking.hooks import share_booking_records


def migrate(cr, version):
    share_booking_records(api.Environment(cr, SUPERUSER_ID, {}))
