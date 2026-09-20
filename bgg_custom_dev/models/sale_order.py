# -*- coding: utf-8 -*-

import datetime
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .calendar_event import CALL_CENTER_APPOINTMENT_REFS

_logger = logging.getLogger(__name__)

DASHBOARD_GROUP = 'bgg_custom_dev.group_bgg_dashboard'
RESPONSABLE_DOSSIER_GROUP = 'bgg_custom_dev.group_responsable_dossier'

# Admin project deadlines (Dossier). Business timezone used to turn the
# confirmation timestamp into a calendar date (Belgian company).
BGG_TZ = 'Europe/Brussels'
# JSON system parameter (see data/admin_project_deadline_params.xml):
# payment term name -> day_type ('business' = Monday to Friday, 'calendar' =
# every day) and the delay in days per product category name (the product's
# category or one of its parents). The defaults below are used when the
# parameter is missing or not valid JSON.
ADMIN_DEADLINE_RULES_PARAM = 'bgg.admin_project_deadline_rules'
ADMIN_DEADLINE_RULES_DEFAULT = {
    'Paiement immédiat': {
        'day_type': 'business',
        'Panneaux': 10, 'Onduleurs': 10, 'Batteries': 10, 'PAC': 15, 'Isolation': 20,
    },
    "50% maintenant, le solde à l'installation": {
        'day_type': 'business',
        'Panneaux': 10, 'Onduleurs': 10, 'Batteries': 10, 'PAC': 15, 'Isolation': 20,
    },
    'Financement': {
        'day_type': 'calendar',
        'Panneaux': 15, 'Onduleurs': 15, 'Batteries': 15, 'PAC': 20, 'Isolation': 25,
    },
    'Financement (Banque/Courtier client)': {
        'day_type': 'calendar',
        'Panneaux': 15, 'Onduleurs': 15, 'Batteries': 15, 'PAC': 20, 'Isolation': 25,
    },
}


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
        """Propagate to the order's projects: a Responsable change (manager /
        assignees) and a payment term change (admin project deadlines)."""
        watched = ('x_responsable_dossier_id', 'payment_term_id')
        previous = {
            fname: {order.id: order[fname] for order in self}
            for fname in watched if fname in vals
        }
        result = super().write(vals)
        if 'x_responsable_dossier_id' in previous:
            for order in self:
                old = previous['x_responsable_dossier_id'][order.id]
                if order.x_responsable_dossier_id != old:
                    order._sync_responsable_dossier(previous_user=old)
        if 'payment_term_id' in previous:
            changed = self.filtered(
                lambda o: o.payment_term_id != previous['payment_term_id'][o.id])
            changed._sync_admin_project_dates()
        return result

    # ------------------------------------------------------------------
    # Admin project deadlines: payment term x product category rules
    # ------------------------------------------------------------------

    @api.model
    def _admin_deadline_json_param(self, key, default):
        """Read a JSON object from a system parameter; fall back to `default`
        (and log) when it is missing or not a JSON object."""
        raw = self.env['ir.config_parameter'].sudo().get_param(key)
        if not raw:
            return default
        try:
            value = json.loads(raw)
        except ValueError:
            _logger.warning("Admin project deadlines: parameter %s is not valid JSON; "
                            "using built-in defaults.", key)
            return default
        if not isinstance(value, dict):
            _logger.warning("Admin project deadlines: parameter %s must be a JSON object; "
                            "using built-in defaults.", key)
            return default
        return value

    @api.model
    def _admin_deadline_rules(self):
        return self._admin_deadline_json_param(
            ADMIN_DEADLINE_RULES_PARAM, ADMIN_DEADLINE_RULES_DEFAULT)

    def _admin_deadline_rule(self):
        """Rule (dict) matching this order's payment term, or None.

        Payment term names are translatable: the term is matched by name,
        case-insensitively, in any installed language.
        """
        self.ensure_one()
        term = self.payment_term_id
        if not term:
            return None
        rules = {str(name).strip().lower(): rule
                 for name, rule in self._admin_deadline_rules().items()
                 if isinstance(rule, dict)}
        names = {term.name}
        for lang_code, _label in self.env['res.lang'].get_installed():
            names.add(term.with_context(lang=lang_code).name)
        for name in names:
            rule = rules.get((name or '').strip().lower())
            if rule is not None:
                return rule
        return None

    @api.model
    def _line_category_match(self, line, names):
        """Lowercased category name of `names` matched by the line's product
        category or one of its parents (case-insensitive), or None."""
        if line.display_type or not line.product_id:
            return None
        categ = line.product_id.categ_id
        while categ:
            name = (categ.name or '').strip().lower()
            if name in names:
                return name
            categ = categ.parent_id
        return None

    def _admin_deadline_delays(self, rule):
        """Delays (days) of `rule` that apply to this order: one per order
        line whose product category (or a parent category) is a key of the
        rule. Category names are matched case-insensitively."""
        self.ensure_one()
        delay_by_category = {}
        for key, value in rule.items():
            if key == 'day_type':
                continue
            try:
                delay_by_category[str(key).strip().lower()] = int(value)
            except (TypeError, ValueError):
                continue
        delays = []
        for line in self.order_line:
            name = self._line_category_match(line, delay_by_category)
            if name is not None:
                delays.append(delay_by_category[name])
        return delays

    @api.model
    def _admin_deadline_all_category_names(self):
        """Lowercased product category names listed in any deadline rule:
        the categories that require an admin project (installation)."""
        names = set()
        for rule in self._admin_deadline_rules().values():
            if isinstance(rule, dict):
                names.update(str(k).strip().lower() for k in rule if k != 'day_type')
        return names

    # ------------------------------------------------------------------
    # Form warnings (Dossier)
    # ------------------------------------------------------------------

    x_installation_product_missing = fields.Boolean(
        string='Produit installation manquant',
        compute='_compute_installation_product_missing',
        help="Vrai quand la commande contient des produits à installer "
             "(catégories des règles de délais) mais aucun service créant le "
             "projet admin (produit d'installation, suivi « Projet »), et "
             "qu'aucun projet admin n'existe pour la commande.",
    )

    @api.depends('order_line.product_id', 'order_line.product_id.service_tracking', 'state')
    def _compute_installation_product_missing(self):
        names = self._admin_deadline_all_category_names()
        for order in self:
            has_hardware = any(
                order._line_category_match(line, names) is not None
                for line in order.order_line)
            has_installation = any(
                line.product_id.service_tracking == 'project_only'
                for line in order.order_line if line.product_id)
            missing = has_hardware and not has_installation
            if missing and order.id and order.state == 'sale':
                missing = not order._get_dossier_projects()
            order.x_installation_product_missing = missing

    @api.model
    def _add_business_days(self, date, days):
        """`date` + `days` business days (Monday to Friday, no holidays)."""
        result = date
        while days > 0:
            result += datetime.timedelta(days=1)
            if result.weekday() < 5:
                days -= 1
        return result

    def _admin_deadline_start_date(self):
        """Signature du BC: the confirmation date (date_order, which sale sets
        to now on confirmation) as a Belgian calendar date."""
        self.ensure_one()
        if not self.date_order:
            return None
        return fields.Datetime.context_timestamp(
            self.with_context(tz=BGG_TZ), self.date_order).date()

    def _compute_admin_project_dates(self):
        """(date_start, date_end) for the admin project of this order, or None
        when no rule applies: no rule for the payment term, or no product of a
        category listed in the rule. With several categories on the order the
        longest delay wins."""
        self.ensure_one()
        start = self._admin_deadline_start_date()
        rule = self._admin_deadline_rule()
        if not start or not rule:
            return None
        delays = self._admin_deadline_delays(rule)
        if not delays:
            return None
        days = max(delays)
        if rule.get('day_type') == 'calendar':
            end = start + datetime.timedelta(days=days)
        else:
            end = self._add_business_days(start, days)
        return start, end

    def _sync_admin_project_dates(self):
        """Apply the computed dates to the order's projects and the deadlines
        of their open tasks. Orders without an applicable rule are left as
        they are (no dates written, nothing cleared)."""
        for order in self:
            dates = order._compute_admin_project_dates()
            if not dates:
                continue
            projects = order._get_dossier_projects()
            if projects:
                projects._apply_admin_project_dates(*dates)

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
