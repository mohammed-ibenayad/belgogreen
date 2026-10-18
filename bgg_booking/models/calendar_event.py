# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.fields import Domain


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    @api.model
    def _search(self, domain, *args, **kwargs):
        """While resource_booking computes availabilities, a cancelled RDV
        does not keep the commercial busy: its meeting is kept for the
        history (see resource.booking.action_cancel) but the slot is free."""
        if self.env.context.get('analyzing_booking'):
            domain = Domain.AND([domain, [('x_rdv_status', '!=', 'cancelled')]])
        return super()._search(domain, *args, **kwargs)
