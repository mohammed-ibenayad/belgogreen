# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models

from .calendar_event import CALL_CENTER_APPOINTMENT_REFS

_logger = logging.getLogger(__name__)

DASHBOARD_GROUP = 'bgg_custom_dev.group_bgg_dashboard'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_call_center_sale_owner_id = fields.Many2one(
        'res.partner',
        string='Call Center (Sale Owner)',
        compute='_compute_call_center_attribution',
        store=True,
        readonly=True,
        groups=DASHBOARD_GROUP,
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

    x_call_center_source_event_id = fields.Many2one(
        'calendar.event',
        string='RDV retenu (Call Center)',
        compute='_compute_call_center_attribution',
        store=True,
        readonly=True,
        groups=DASHBOARD_GROUP,
        help="The calendar event that drove the Call Center (Sale Owner) attribution.",
    )

    x_call_center_candidate_event_ids = fields.Many2many(
        'calendar.event',
        string='RDV candidats (Call Center)',
        compute='_compute_call_center_candidate_event_ids',
        store=False,
        groups=DASHBOARD_GROUP,
        help="All call-center appointments considered by the attribution logic for this sale.",
    )

    x_call_center_event_count = fields.Integer(
        string='RDV Call Center',
        compute='_compute_call_center_event_count',
        store=False,
        groups=DASHBOARD_GROUP,
    )

    # ------------------------------------------------------------------
    # Helper shared by every compute: gather the candidate calendar.events
    # ------------------------------------------------------------------

    def _get_call_center_candidate_events(self):
        """Return the calendar.event recordset considered for attribution.

        Uses the same input rules as the compute so "what is shown" and
        "what was picked" never disagree:
        - Via opportunity if set, otherwise fallback seller + client search.
        - Always restricted to call-center appointment types.
        - No tiebreakers applied here — returns the full candidate list.
        """
        self.ensure_one()
        call_center_type_ids = self.env['appointment.type'].search([
            ('x_appointment_ref', 'in', CALL_CENTER_APPOINTMENT_REFS),
        ]).ids
        CalendarEvent = self.env['calendar.event']

        if not call_center_type_ids:
            return CalendarEvent.browse()

        if self.opportunity_id:
            return self.opportunity_id.calendar_event_ids.filtered(
                lambda e: e.appointment_type_id.id in call_center_type_ids
            )

        if self.user_id and self.partner_id:
            return CalendarEvent.search([
                ('user_id', '=', self.user_id.id),
                ('partner_ids', 'in', self.partner_id.id),
                ('appointment_type_id', 'in', call_center_type_ids),
            ])

        return CalendarEvent.browse()

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

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
    def _compute_call_center_attribution(self):
        """Compute both the owner partner and the winning event together."""
        call_center_group = self.env['res.groups'].search([
            ('name', '=', 'Call Center'),
        ], limit=1)
        call_center_group_id = call_center_group.id if call_center_group else False

        for order in self:
            candidates = order._get_call_center_candidate_events()
            event = self._select_best_call_center_event(candidates, order.date_order)

            owner = self.env['res.partner']
            if event:
                if event.x_studio_rendez_vous_pris_la_place_de:
                    owner = event.x_studio_rendez_vous_pris_la_place_de
                elif (event.create_uid
                      and call_center_group_id
                      and call_center_group_id in event.create_uid.group_ids.ids):
                    owner = event.create_uid.partner_id

            order.x_call_center_sale_owner_id = owner or False
            order.x_call_center_source_event_id = event or False

    @api.depends(
        'opportunity_id',
        'opportunity_id.calendar_event_ids',
        'opportunity_id.calendar_event_ids.appointment_type_id',
        'user_id',
        'partner_id',
    )
    def _compute_call_center_candidate_event_ids(self):
        for order in self:
            order.x_call_center_candidate_event_ids = order._get_call_center_candidate_events()

    @api.depends('x_call_center_candidate_event_ids')
    def _compute_call_center_event_count(self):
        for order in self:
            order.x_call_center_event_count = len(order.x_call_center_candidate_event_ids)

    # ------------------------------------------------------------------
    # Tiebreakers (unchanged behavior)
    # ------------------------------------------------------------------

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
            return events[:1]

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

    # ------------------------------------------------------------------
    # Action for the smart button
    # ------------------------------------------------------------------

    def action_open_call_center_events(self):
        """Open the list of call-center appointments considered for this sale."""
        self.ensure_one()
        event_ids = self.x_call_center_candidate_event_ids.ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('RDV Call Center'),
            'res_model': 'calendar.event',
            'view_mode': 'list,form',
            'domain': [('id', 'in', event_ids)],
            'context': {'create': False},
        }
