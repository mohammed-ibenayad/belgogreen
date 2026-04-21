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

            # 3) Resolve: "pris à la place de" on the event wins over its create_uid
            if event:
                pris_a_la_place = event.x_studio_rendez_vous_pris_la_place_de
                if pris_a_la_place:
                    order.x_call_center_sale_owner_id = pris_a_la_place
                elif event.create_uid:
                    order.x_call_center_sale_owner_id = event.create_uid.partner_id
                else:
                    order.x_call_center_sale_owner_id = False
            else:
                order.x_call_center_sale_owner_id = False

    @api.model
    def _select_best_call_center_event(self, events, date_order):
        """Pick one calendar.event from `events` using the agreed tiebreakers.

        1. Prefer events in the same month/year as `date_order` with
           appointment_status == 'attended'. If non-empty, restrict to that subset.
        2. Among the remaining, pick the one whose `start` is closest to
           `date_order`. Events without a `start` are pushed to the end.
        """
        if not events or len(events) == 1:
            return events

        if date_order:
            same_month_attended = events.filtered(
                lambda e: e.appointment_status == 'attended'
                and e.start
                and e.start.month == date_order.month
                and e.start.year == date_order.year
            )
            if same_month_attended:
                events = same_month_attended

        if len(events) == 1 or not date_order:
            return events[:1]

        def distance(ev):
            if not ev.start:
                return float('inf')
            return abs((ev.start - date_order).total_seconds())

        return events.sorted(key=distance)[:1]
