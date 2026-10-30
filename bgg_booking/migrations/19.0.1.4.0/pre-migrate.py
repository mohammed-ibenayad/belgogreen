# -*- coding: utf-8 -*-
"""The "Call Center" and "RDV Commercial" top-level menus made by hand
(links to the Enterprise booking pages) are adopted, so the module's
menus repoint them to "Prise de RDV". Same as the pre-install hook, for
databases where bgg_booking is already installed."""

from odoo.addons.bgg_booking.hooks import adopt_booking_menus


def migrate(cr, version):
    adopt_booking_menus(cr)
