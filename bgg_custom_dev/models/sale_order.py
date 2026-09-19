# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .calendar_event import CALL_CENTER_APPOINTMENT_REFS

_logger = logging.getLogger(__name__)

DASHBOARD_GROUP = 'bgg_custom_dev.group_bgg_dashboard'
RESPONSABLE_DOSSIER_GROUP = 'bgg_custom_dev.group_responsable_dossier'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # Dossier tab: Responsable (project manager of the sale order)
    # ------------------------------------------------------------------
    # Business wording is French on purpose ("Dossier", "Responsable",
    # "Responsable Dossier") and must not be translated. The Responsable is
    # the internal user who follows up the admins' activities and the field
    # service until the order is delivered to the client.

    x_responsable_dossier_id = fields.Many2one(
        'res.users',
        string='Responsable',
        tracking=True,
        index='btree_not_null',
        domain=lambda self: self._responsable_dossier_domain(),
        help=(
            "Responsable du dossier : personne chargée du suivi des "
            "activités des admins et du service sur site jusqu'à la "
            "livraison de la commande au client. "
            "Seuls les utilisateurs internes du groupe « Responsable "
            "Dossier » peuvent être sélectionnés. "
            "Le Responsable devient chef de projet des projets liés à la "
            "commande et est assigné à toutes leurs tâches ouvertes."
        ),
    )

    def write(self, vals):
        """Propagate a Responsable change to the projects of the order."""
        if 'x_responsable_dossier_id' not in vals:
            return super().write(vals)
        previous = {order.id: order.x_responsable_dossier_id for order in self}
        result = super().write(vals)
        for order in self:
            if order.x_responsable_dossier_id != previous[order.id]:
                order._sync_responsable_dossier(previous_user=previous[order.id])
        return result

    def _get_dossier_projects(self):
        """Projects created for / linked to this order (same links as the
        standard sale.order.project_ids compute), templates excluded."""
        self.ensure_one()
        return self.env['project.project'].sudo().search([
            '|',
            ('sale_line_id.order_id', '=', self.id),
            ('reinvoiced_sale_order_id', '=', self.id),
            ('is_template', '=', False),
        ])

    def _sync_responsable_dossier(self, previous_user=None):
        """Apply the order's Responsable to its projects: project manager on
        the projects, assignee on their open tasks (the previous Responsable
        is unassigned from those tasks)."""
        for order in self:
            projects = order._get_dossier_projects()
            if projects:
                projects._apply_responsable_dossier(
                    order.x_responsable_dossier_id, previous_user)

    @api.model
    def _responsable_dossier_domain(self):
        """Domain restricting the Responsable to internal users that belong
        (directly or through implied groups) to the Responsable Dossier group.
        """
        group = self.env.ref(RESPONSABLE_DOSSIER_GROUP, raise_if_not_found=False)
        domain = [('share', '=', False)]
        if group:
            domain.append(('all_group_ids', 'in', group.id))
        return domain

    @api.constrains('x_responsable_dossier_id')
    def _check_responsable_dossier(self):
        """Server-side counterpart of the client-side domain: the Responsable
        must be an internal user of the Responsable Dossier group (imports,
        RPC and server actions bypass the view domain).
        """
        orders = self.filtered('x_responsable_dossier_id')
        if not orders:
            return
        group = self.env.ref(RESPONSABLE_DOSSIER_GROUP, raise_if_not_found=False)
        for order in orders:
            user = order.x_responsable_dossier_id
            if user.share or (group and not user.has_group(RESPONSABLE_DOSSIER_GROUP)):
                raise ValidationError(_(
                    "%(user)s ne peut pas être Responsable du dossier %(order)s : "
                    "seuls les utilisateurs internes du groupe « Responsable "
                    "Dossier » peuvent être sélectionnés.",
                    user=user.name, order=order.name,
                ))

    x_call_center_sale_owner_id = fields.Many2one(
        'res.partner',
        string='Call Center (Sale Owner)',
        compute='_compute_call_center_attribution',
        store=True,
        readonly=True,
        groups=DASHBOARD_GROUP,
        help=(
            "Call center credited for this sale. "
            "Candidates are every RDV related to the sale (linked to its "
            "opportunity, or matching seller + client) whose start is at or "
            "before date_order — regardless of appointment type. "
            "If multiple candidates exist, the ones with appointment_status "
            "= 'attended' are preferred; among those, the one whose start is "
            "closest to date_order wins. "
            "From the winning RDV: x_studio_rendez_vous_pris_la_place_de "
            "wins if set; otherwise the winner must be of a call-center "
            "appointment type AND its create_uid must be in the 'Call Center' "
            "group, in which case create_uid.partner_id is the call center. "
            "Anything else leaves the field empty."
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

        Pattern B scope: any RDV related to the sale, regardless of
        appointment type, whose start is at or before date_order.
        - Linked to opportunity_id.calendar_event_ids if there is one,
        - otherwise found by (user_id = sale.user_id, partner_ids ∋ sale.partner_id).

        Selection (which one wins) and resolution (whether it produces a
        call-center attribution) live in _select_best_call_center_event and
        _compute_call_center_attribution respectively.
        """
        self.ensure_one()
        CalendarEvent = self.env['calendar.event']

        if self.opportunity_id:
            events = self.opportunity_id.calendar_event_ids
        elif self.user_id and self.partner_id:
            events = CalendarEvent.search([
                ('user_id', '=', self.user_id.id),
                ('partner_ids', 'in', self.partner_id.id),
            ])
        else:
            return CalendarEvent.browse()

        if self.date_order:
            events = events.filtered(
                lambda e: e.start and e.start <= self.date_order
            )
        return events

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
        call_center_type_ids = self.env['appointment.type'].search([
            ('x_appointment_ref', 'in', CALL_CENTER_APPOINTMENT_REFS),
        ]).ids
        call_center_group = self.env['res.groups'].search([
            ('name', '=', 'Call Center'),
        ], limit=1)
        call_center_group_id = call_center_group.id if call_center_group else False

        for order in self:
            candidates = order._get_call_center_candidate_events()
            event = self._select_best_call_center_event(candidates, order.date_order)

            owner = self.env['res.partner']
            if event:
                # 1) Explicit override on the winning RDV — takes precedence
                #    regardless of appointment type.
                if event.x_studio_rendez_vous_pris_la_place_de:
                    owner = event.x_studio_rendez_vous_pris_la_place_de
                # 2) Default attribution: only if the winner is of a
                #    call-center appointment type AND was created by a user in
                #    the "Call Center" group. This is what voids attribution
                #    when the salesperson took over with a commercial RDV.
                elif (event.appointment_type_id.id in call_center_type_ids
                      and event.create_uid
                      and call_center_group_id
                      and call_center_group_id in event.create_uid.group_ids.ids):
                    owner = event.create_uid.partner_id

            order.x_call_center_sale_owner_id = owner or False
            order.x_call_center_source_event_id = event or False

    @api.depends(
        'opportunity_id',
        'opportunity_id.calendar_event_ids',
        'opportunity_id.calendar_event_ids.start',
        'user_id',
        'partner_id',
        'date_order',
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
        """Pick one calendar.event from `events` (already pre-filtered to
        start <= date_order by `_get_call_center_candidate_events`).

        - 0 candidates → return empty.
        - 1 candidate → it wins, status-blind.
        - 2+ candidates → prefer those with appointment_status = 'attended';
          if any qualify, restrict to that subset. Then pick the one whose
          start is closest to date_order.
        """
        if not events:
            return events
        if len(events) == 1 or not date_order:
            return events[:1]

        attended = events.filtered(lambda e: e.appointment_status == 'attended')
        if attended:
            events = attended

        def distance(ev):
            return abs((ev.start - date_order).total_seconds()) if ev.start else float('inf')

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
