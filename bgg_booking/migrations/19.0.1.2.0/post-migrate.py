# -*- coding: utf-8 -*-
""""Réservable par" of the existing study types: the call centre for the
CNT types, the commercials for the COM types."""

from odoo import SUPERUSER_ID, api

from odoo.addons.bgg_booking.hooks import set_booking_type_roles


def migrate(cr, version):
    set_booking_type_roles(api.Environment(cr, SUPERUSER_ID, {}))
