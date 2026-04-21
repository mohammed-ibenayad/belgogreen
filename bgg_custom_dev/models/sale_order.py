# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models

from .calendar_event import CALL_CENTER_APPOINTMENT_REFS

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_call_center_sale_owner_id = fields.Many2one(
        'res.partner',
        string='Call Center (Sale Owner)',
        compute='_compute_x_call_center_sale_owner_id',
        store=True,
        readonly=True,
        help=(
            "Call center credited for this sale. Resolution: "
            "(1) find the relevant call-center appointment — via the sale's "
            "opportunity if present, otherwise by matching the sale's "
            "salesperson + client. "
            "(2) On that appointment, if `x_studio_rendez_vous_pris_la_place_de` "
            "is set, use it (the real call center the RDV was booked on behalf "
            "of); otherwise fall back to `create_uid.partner_id` (the booker). "
            "When multiple appointments match, prefer those in the sale's month "
            "with status 'attended', then the one whose start is closest to "
            "date_order."
        ),
    )

    @api.depends(
        'opportunity_id',
        'opportunity_id.calendar_event_ids',
        'opportunity_id.calendar_event_ids.create_uid',
        'opportunity_id.calendar_event_ids.appointment_type_id',
        'opportunity_id.calendar_event_ids.appointment_status',
        'opportunity_id.calendar_event_ids.start',
        'opportunity_id.calendar_event_ids.x_studio_rendez_vous_pris_la_place_de',
        'user_id',
        'partner_id',
        'date_order',
    )
    def _compute_x_call_center_sale_owner_id(self):
        call_center_type_ids = self.env['appointment.type'].search([
            ('x_appointment_ref', 'in', CALL_CENTER_APPOINTMENT_REFS),
        ]).ids
        call_center_group = self.env['res.groups'].search([
            ('name', '=', 'Call Center'),
        ], limit=1)
        call_center_group_id = call_center_group.id if call_center_group else False
        CalendarEvent = self.env['calendar.event']

        for order in self:
            event = CalendarEvent

            # 1) Main case: via opportunity
            if order.opportunity_id and call_center_type_ids:
                events = order.opportunity_id.calendar_event_ids.filtered(
                    lambda e: e.appointment_type_id.id in call_center_type_ids
                )
                event = self._select_best_call_center_event(events, order.date_order)

            # 2) Fallback: no opportunity or no matching event → search by seller + client
            if (not event
                    and call_center_type_ids
                    and order.user_id
                    and order.partner_id):
                candidates = CalendarEvent.search([
                    ('user_id', '=', order.user_id.id),
                    ('partner_ids', 'in', order.partner_id.id),
                    ('appointment_type_id', 'in', call_center_type_ids),
                ])
                event = self._select_best_call_center_event(candidates, order.date_order)

            # 3) Resolve the selected event to a call-center partner.
            #    - pris-à-la-place-de wins if set (already a partner).
            #    - else create_uid.partner_id, but only if create_uid is in the
            #      "Call Center" res.groups. Otherwise leave empty.
            owner = self.env['res.partner']
            if event:
                if event.x_studio_rendez_vous_pris_la_place_de:
                    owner = event.x_studio_rendez_vous_pris_la_place_de
                elif (event.create_uid
                      and call_center_group_id
                      and call_center_group_id in event.create_uid.group_ids.ids):
                    owner = event.create_uid.partner_id
            order.x_call_center_sale_owner_id = owner or False

    @api.model
    def _select_best_call_center_event(self, events, date_order):
        """Pick one calendar.event from `events` using the agreed tiebreakers.

        Rules applied in order:
        - RDV must have happened at or before `date_order`. Future RDVs can't
          have driven the sale, so they're dropped.
        - Keep only events whose `start` is in the sale's month/year AND whose
          `appointment_status == 'attended'`. If that subset is empty, return
          an empty recordset (no attribution).
        - Among the remaining, pick the event whose `start` is closest to
          `date_order`. Ties fall back to recordset order.
        """
        if not events:
            return events
        if not date_order:
            # Without a sale date we cannot apply the ordering filters;
            # fall back to the first candidate.
            return events[:1]

        # Drop RDVs after the sale — they can't have originated it.
        events = events.filtered(
            lambda e: e.start and e.start <= date_order
        )
        if not events:
            return events.browse()

        same_month_attended = events.filtered(
            lambda e: e.appointment_status == 'attended'
            and e.start.month == date_order.month
            and e.start.year == date_order.year
        )
        if not same_month_attended:
            return events.browse()
        events = same_month_attended

        if len(events) == 1:
            return events

        def distance(ev):
            return abs((ev.start - date_order).total_seconds())

        return events.sorted(key=distance)[:1]
