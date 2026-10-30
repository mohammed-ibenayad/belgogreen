# -*- coding: utf-8 -*-

import datetime
import json
import logging
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .calendar_event import CALL_CENTER_APPOINTMENT_REFS

_logger = logging.getLogger(__name__)

DASHBOARD_GROUP = 'bgg_custom_dev.group_bgg_dashboard'

# Order states that mean "confirmed" (x_was_confirmed is set on them).
CONFIRMED_STATES = ('sale', 'done')


def dashboard_states_domain(states):
    """Domain on the order state for the dashboards (Suivi Commercial, Call
    Center, AMSS): a cancelled order counts only if it was confirmed before
    (x_was_confirmed); a quote cancelled before signature is not a sale."""
    domain = [('state', 'in', list(states))]
    if 'cancel' in states:
        domain += ['|', ('state', '!=', 'cancel'), ('x_was_confirmed', '=', True)]
    return domain
RESPONSABLE_DOSSIER_GROUP = 'bgg_custom_dev.group_responsable_dossier'
# Only members of this group may set or change the Responsable of an order
# (no administrator exception). Automations (sudo) are not restricted.
RESPONSABLE_DOSSIER_ADMIN_GROUP = 'bgg_custom_dev.group_responsable_dossier_admin'

# Admin project deadlines (Dossier). Business timezone used to turn the
# confirmation timestamp into a calendar date (Belgian company).
BGG_TZ = 'Europe/Brussels'
# JSON system parameters (see data/admin_project_deadline_params.xml). The
# defaults below are used when a parameter is missing or not valid JSON.
#
# bgg.admin_project_deadline_rules: payment term name -> rule
#   - 'sss': reference dates of the field service (SSS) project, computed in
#     memory only, never written: 'start_offset' (+ 'start_day_type') from the
#     confirmation date, then 'day_type' and '<product category name>':
#     duration (the product's category or one of its parents; the longest
#     duration on the order wins). The category names listed here are also
#     the products that need an installation (form warning).
#   - 'end_offset' and 'day_type': admin project end date = SSS reference end
#     date + 'end_offset' days, counted as 'business' (Monday to Friday) or
#     'calendar' (every day) days.
# bgg.admin_task_deadline_rules: admin template tasks whose dates follow the
#   SSS reference end date: 'day_type' and 'tasks': {task name: offset days}.
#   Task names are matched ignoring case, accents and extra spaces. Start of
#   the task = SSS end, deadline = SSS end + offset.
ADMIN_DEADLINE_RULES_PARAM = 'bgg.admin_project_deadline_rules'
ADMIN_TASK_RULES_PARAM = 'bgg.admin_task_deadline_rules'
# Keys of a rule that are not product category names.
RULE_RESERVED_KEYS = {'day_type', 'sss', 'start_offset', 'start_day_type', 'end_offset'}
# Admin project end = SSS end + this many days when a rule has no 'end_offset'.
ADMIN_END_OFFSET_DEFAULT = 10

_IMMEDIATE_RULE = {
    'day_type': 'business',
    'end_offset': ADMIN_END_OFFSET_DEFAULT,
    'sss': {
        'start_offset': 5, 'start_day_type': 'business', 'day_type': 'business',
        'Panneaux': 5, 'Onduleurs': 5, 'Batteries': 5, 'PAC': 10, 'Isolation': 15,
    },
}
_FINANCING_RULE = {
    'day_type': 'business',
    'end_offset': ADMIN_END_OFFSET_DEFAULT,
    'sss': {
        'start_offset': 10, 'start_day_type': 'business', 'day_type': 'business',
        'Panneaux': 25, 'Onduleurs': 25, 'Batteries': 25, 'PAC': 30, 'Isolation': 35,
    },
}
ADMIN_DEADLINE_RULES_DEFAULT = {
    'Paiement immédiat': _IMMEDIATE_RULE,
    "50% maintenant, le solde à l'installation": _IMMEDIATE_RULE,
    'Financement': _FINANCING_RULE,
    'Financement (Banque/Courtier client)': _FINANCING_RULE,
}
ADMIN_TASK_RULES_DEFAULT = {
    'day_type': 'business',
    'tasks': {
        'Réclamation du solde': 0,
        'Création des commissions': 0,
        'Chargement schéma unifilaire': 5,
        'Envoi Belgotest + coordonnées RESA / ORES': 10,
    },
}


def normalize_task_name(name):
    """Task name comparison key: no accents, case-folded, single spaces."""
    text = unicodedata.normalize('NFKD', name or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return ' '.join(text.casefold().split())


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

    # Set when the order is confirmed, kept when it is cancelled: tells a sale
    # cancelled after signature from a quote cancelled before (dashboards).
    # Existing orders are filled from the status history by the 19.0.1.28.0
    # migration.
    x_was_confirmed = fields.Boolean(
        string='Confirmée au moins une fois',
        readonly=True,
        copy=False,
        index=True,
        help=(
            "Cochée dès que la commande est confirmée et conservée si elle est "
            "annulée ensuite. Les tableaux de bord ne comptent une commande "
            "annulée comme vente annulée que si elle a été confirmée."
        ),
    )

    def write(self, vals):
        """Propagate to the order's projects: a Responsable change (manager /
        assignees) and a payment term change (admin project deadlines)."""
        if vals.get('state') in CONFIRMED_STATES:
            vals = dict(vals, x_was_confirmed=True)
        watched = ('x_responsable_dossier_id', 'payment_term_id')
        previous = {
            fname: {order.id: order[fname] for order in self}
            for fname in watched if fname in vals
        }
        if 'x_responsable_dossier_id' in previous:
            new_id = vals['x_responsable_dossier_id'] or False
            if any(previous['x_responsable_dossier_id'][o.id].id != new_id for o in self):
                self._check_responsable_dossier_edit_allowed()
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
            if key in RULE_RESERVED_KEYS:
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
        """Lowercased product category names listed in the 'sss' block of any
        deadline rule: the categories that require an admin project
        (installation)."""
        names = set()
        for rule in self._admin_deadline_rules().values():
            sss = rule.get('sss') if isinstance(rule, dict) else None
            if isinstance(sss, dict):
                names.update(str(k).strip().lower() for k in sss
                             if k not in RULE_RESERVED_KEYS)
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

    @api.model
    def _add_days(self, date, days, day_type):
        """`date` + `days`, counted as calendar days when `day_type` is
        'calendar', as business days otherwise."""
        if day_type == 'calendar':
            return date + datetime.timedelta(days=days)
        return self._add_business_days(date, days)

    @api.model
    def _admin_task_rules(self):
        return self._admin_deadline_json_param(
            ADMIN_TASK_RULES_PARAM, ADMIN_TASK_RULES_DEFAULT)

    def _compute_sss_reference_dates(self):
        """Reference (start, end) dates of the field service (SSS) project
        for this order, from the 'sss' block of the payment term rule:
        start = confirmation date + start_offset, end = start + the longest
        category duration on the order. Computed in memory only. None when
        no rule applies."""
        self.ensure_one()
        bc_date = self._admin_deadline_start_date()
        rule = self._admin_deadline_rule()
        sss = rule.get('sss') if rule else None
        if not bc_date or not isinstance(sss, dict):
            return None
        delays = self._admin_deadline_delays(sss)
        if not delays:
            return None
        try:
            start_offset = int(sss.get('start_offset', 0))
        except (TypeError, ValueError):
            start_offset = 0
        start = self._add_days(
            bc_date, start_offset, sss.get('start_day_type', sss.get('day_type')))
        end = self._add_days(start, max(delays), sss.get('day_type'))
        return start, end

    def _compute_admin_task_dates(self):
        """{normalized task name: (start, deadline)} for the admin template
        tasks that follow the SSS reference end date: start = SSS end,
        deadline = SSS end + the task's offset. Empty when no rule applies."""
        self.ensure_one()
        sss_dates = self._compute_sss_reference_dates()
        if not sss_dates:
            return {}
        _sss_start, sss_end = sss_dates
        rules = self._admin_task_rules()
        tasks = rules.get('tasks') if isinstance(rules, dict) else None
        if not isinstance(tasks, dict):
            return {}
        result = {}
        for name, offset in tasks.items():
            try:
                offset = int(offset)
            except (TypeError, ValueError):
                continue
            key = normalize_task_name(str(name))
            if key:
                result[key] = (sss_end, self._add_days(sss_end, offset, rules.get('day_type')))
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
        category listed in its 'sss' block. Start = confirmation date, end =
        SSS reference end date + the rule's 'end_offset' (the SSS end already
        follows the longest category duration on the order)."""
        self.ensure_one()
        start = self._admin_deadline_start_date()
        sss_dates = self._compute_sss_reference_dates()
        if not start or not sss_dates:
            return None
        rule = self._admin_deadline_rule()
        try:
            end_offset = int(rule.get('end_offset', ADMIN_END_OFFSET_DEFAULT))
        except (TypeError, ValueError):
            end_offset = ADMIN_END_OFFSET_DEFAULT
        _sss_start, sss_end = sss_dates
        end = self._add_days(sss_end, end_offset, rule.get('day_type'))
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
                projects._apply_admin_project_dates(
                    *dates, task_dates=order._compute_admin_task_dates())

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

    # View helper: True when the current user may set or change the
    # Responsable (member of Responsable Dossier Admin).
    x_user_can_edit_responsable_dossier = fields.Boolean(
        string='Current User Can Edit Responsable',
        compute='_compute_user_can_edit_responsable_dossier',
    )

    @api.depends_context('uid')
    def _compute_user_can_edit_responsable_dossier(self):
        can_edit = self._user_can_edit_responsable_dossier()
        for order in self:
            order.x_user_can_edit_responsable_dossier = can_edit

    @api.model
    def _user_can_edit_responsable_dossier(self):
        # Group members only (no administrator exception); automations run in
        # sudo and are not restricted.
        return self.env.su or self.env.user.has_group(RESPONSABLE_DOSSIER_ADMIN_GROUP)

    def _check_responsable_dossier_edit_allowed(self):
        """Raise unless the current user may set or change the Responsable."""
        if not self._user_can_edit_responsable_dossier():
            raise UserError(
                "Seuls les membres du groupe « Responsable Dossier Admin » peuvent "
                "désigner ou modifier le Responsable du dossier."
            )

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('x_responsable_dossier_id') for vals in vals_list):
            self._check_responsable_dossier_edit_allowed()
        vals_list = [dict(vals, x_was_confirmed=True) if vals.get('state') in CONFIRMED_STATES
                     else vals for vals in vals_list]
        return super().create(vals_list)

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
            "If multiple candidates exist, the ones with x_rdv_status "
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
        'opportunity_id.calendar_event_ids.x_rdv_type_id',
        'opportunity_id.calendar_event_ids.x_rdv_status',
        'opportunity_id.calendar_event_ids.start',
        'opportunity_id.calendar_event_ids.x_studio_rendez_vous_pris_la_place_de',
        'user_id',
        'partner_id',
        'date_order',
    )
    def _compute_call_center_attribution(self):
        """Compute both the owner partner and the winning event together."""
        call_center_type_ids = self.env['bgg.rdv.type'].search([
            ('code', 'in', CALL_CENTER_APPOINTMENT_REFS),
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
                elif (event.x_rdv_type_id.id in call_center_type_ids
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
        - 2+ candidates → prefer those with x_rdv_status = 'attended';
          if any qualify, restrict to that subset. Then pick the one whose
          start is closest to date_order.
        """
        if not events:
            return events
        if len(events) == 1 or not date_order:
            return events[:1]

        attended = events.filtered(lambda e: e.x_rdv_status == 'attended')
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
