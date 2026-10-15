# -*- coding: utf-8 -*-

import base64
import io
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .commercial_dashboard import CALL_CENTER_APPOINTMENT_REFS, COMMERCIAL_APPOINTMENT_REFS
from .project_update import BLOCKED_STATUS
from .sale_order import BGG_TZ, dashboard_states_domain

_logger = logging.getLogger(__name__)

DIRECTION_GROUP = 'bgg_custom_dev.group_direction'
# "Commercial" group (created outside the module, linked to this xmlid by the
# post-init hook, see hooks.py).
COMMERCIAL_GROUP = 'bgg_custom_dev.group_commercial'
OTHER_SALESPEOPLE = 'autres'

MONTH_NAMES_FR = {
    1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril', 5: 'mai', 6: 'juin',
    7: 'juillet', 8: 'août', 9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre',
}

# Tooltips. The figures that exist in Suivi Commercial keep its names and
# tooltips word for word (static/src/xml/commercial_dashboard.xml).
TOOLTIPS = {
    'ca_net': "CA NET = CA BRUT − CA ANNULÉ.",
    'ventes_confirmees': (
        "Ventes Confirmées = nombre de commandes à l'état Confirmé ou "
        "Verrouillé (state ∈ {sale, done})."),
    'tx_conversion': (
        "TX CONVERSION = (Ventes Confirmées + Ventes Annulées) / (Présents Call "
        "+ Présents Commercial). Les annulations ultérieures sont incluses au "
        "numérateur pour refléter la capacité de transformation du commercial "
        "(le suivi des annulations se fait via TX ANNULATION). Non filtré par "
        "condition de paiement : les RDV n'ont pas de condition de paiement. "
        "Cliquer : les RDV Présents de la période (dénominateur)."),
    'ventes_annulees': (
        "Ventes Annulées = nombre de commandes de la période annulées après "
        "avoir été confirmées (comme dans Suivi Commercial). Un devis annulé "
        "avant signature ne compte pas."),
    'chantiers_retard': (
        "Chantiers en retard = projets admin (commandes confirmées) ayant au "
        "moins une tâche ouverte dont l'échéance dépasse la date de fin du "
        "projet, ou encore ouverte après cette date. Situation à ce jour."),
    'dossiers_bloques': (
        "Dossiers bloqués = projets admin dont le dernier statut est « Bloqué » "
        "(bloqués à la main ou par une tâche bloquée) "
        "(à ce jour, ou à la fin de la période si elle est terminée). "
        "Comparaison : nombre à la fin de la période précédente."),
    'signe': (
        "Signé = CA NET : somme HT des commandes confirmées dans la période "
        "(state ∈ {sale, done})."),
    'facture': (
        "Facturé = somme HT des factures clients comptabilisées de ces "
        "commandes, avoirs déduits."),
    'encaisse': (
        "Encaissé = part HT effectivement payée de ces factures (paiements "
        "partiels inclus, au prorata), avoirs déduits."),
    'reste_a_facturer': (
        "Reste à facturer (zone grise des barres Facturé et Encaissé) = pour "
        "chaque commande, montant HT des quantités pas encore facturées "
        "(factures clients comptabilisées), acomptes facturés déduits. Un "
        "avoir ne remet jamais de quantités « à facturer » (il réduit ce qui "
        "est dû) ; une facture entièrement annulée par un avoir compte comme "
        "non facturée. Liste : ces commandes."),
    'reste_a_encaisser': (
        "Reste à encaisser = Facturé − Encaissé (zone claire de la barre "
        "Encaissé). Liste : les factures et avoirs de ces commandes pas encore "
        "entièrement payés."),
    'recouvrement_facturer': (
        "Reste à facturer (à ce jour) = pour chaque commande confirmée, toutes "
        "dates de signature : montant HT des quantités pas encore facturées "
        "(factures clients comptabilisées), acomptes facturés déduits. Un "
        "avoir ne remet jamais de quantités « à facturer » ; une facture "
        "entièrement annulée par un avoir compte comme non facturée."),
    'recouvrement_encaisser': (
        "Reste à encaisser (à ce jour) = part HT non payée des factures et "
        "avoirs comptabilisés de toutes les commandes confirmées : montant HT × "
        "reste à payer ÷ montant TTC."),
    'recouvrement_sss': (
        "Reste à encaisser – chantiers SSS terminés (à ce jour) = commandes "
        "confirmées dont le projet SSS (service sur site) a toutes ses tâches "
        "terminées ou annulées (au moins une terminée) : ce que le client doit "
        "encore, HT = reste à facturer de la commande + part non payée de ses "
        "factures et avoirs."),
    'carnet_bloques': (
        "Bloqués = commandes confirmées non terminées dont le projet admin est "
        "au statut « Bloqué »."),
    'carnet_a_planifier': (
        "À planifier = commandes confirmées non terminées, non bloquées, dont le "
        "projet admin n'a pas encore de date de fin (ou qui n'ont pas de projet "
        "admin), ou sans Responsable dossier."),
    'carnet_en_cours': (
        "En cours = commandes planifiées dont au moins une tâche du projet admin "
        "est terminée."),
    'carnet_planifies': (
        "Planifiés = commandes confirmées non terminées avec dates du projet admin "
        "et Responsable dossier, aucune tâche encore terminée."),
    'carnet_total': (
        "Carnet de commandes = commandes confirmées (BC signés) dont le projet "
        "admin n'est pas au statut « Terminé », toutes dates de signature, à ce "
        "jour. Montant = somme HT (comme le CA NET). Chaque commande est dans "
        "une seule ligne : Bloqués, puis À planifier, En cours, Planifiés."),
}

CARNET_ROWS = ('carnet_a_planifier', 'carnet_planifies', 'carnet_en_cours', 'carnet_bloques')

# Métiers tab: métier of an order (see _order_metier). Rule agreed from the
# analysis of the October 2026 orders: Panneaux, Onduleurs and Batteries are
# always sold together (Photovoltaïque), boilers (ballon thermodynamique) go
# with the heat pumps (Chauffage / PAC).
SALEABLE_PATH = ('All', 'Saleable')
METIER_BY_CATEGORY = {               # first level under All / Saleable
    'Panneaux': 'Photovoltaïque',
    'Onduleurs': 'Photovoltaïque',
    'Batteries': 'Photovoltaïque',
    'PAC': 'Chauffage / PAC',
    'Boilers': 'Chauffage / PAC',
    'Isolation': 'Isolation',
}                                    # other sub-categories: their own name
METIER_SALEABLE = 'Autres métiers'   # products directly in All / Saleable (adoucisseur, ventilation…)
METIER_NONE = 'Aucun'                # products without category
METIER_OTHER = 'Autres'              # categories outside All / Saleable (All / Expenses…)
METIER_MIXED = 'Mixte'               # several métiers on the order
# Lines that do not decide the métier of an order: installation services,
# discounts, accessories, expenses, products without category.
METIER_MINOR = {'Services', 'Accessoires', METIER_NONE, METIER_OTHER}
# Products ignored by the rule, whatever their category ("Frais divers" is
# filed under Isolation but used in every métier).
METIER_IGNORED_PRODUCT_CODES = {'FRAIS-DIV'}
TOOLTIPS.update({
    'bc_par_commercial': (
        "BC signés par commercial = VENTES CONFIRMÉES (commandes à l'état "
        "Confirmé ou Verrouillé, state ∈ {sale, done}) de la période par "
        "vendeur de la commande ; membres du groupe Commercial, les autres "
        "vendeurs dans « Autres »."),
    'funnel_rdv_poses': (
        "RDV posés = RDV Call Center + RDV Commercial de la période (Présent, "
        "No-Show, Refusé, Réservé), comme le Total RDV de Suivi Commercial."),
    'funnel_rdv_tenus': "RDV tenus = RDV de la période où le client s'est présenté (Présent).",
    'funnel_bc': (
        "BC signés = Ventes Confirmées + Ventes Annulées de la période (numérateur "
        "du TX CONVERSION) : BC signés / RDV tenus = TX CONVERSION."),
    'panier_moyen': "PANIER MOYEN = CA NET / Ventes Confirmées (comme Suivi Commercial).",
    'panier_metier': (
        "Panier moyen par métier = CA NET des commandes du métier / nombre de ces "
        "commandes (métier de la commande comme dans l'onglet Métiers)."),
    'annulation_signature': (
        "Annulation après signature = Ventes Annulées / (Ventes Confirmées + "
        "Ventes Annulées), en nombre de commandes (TX ANNULATION de Suivi "
        "Commercial est en montant)."),
    'filtre_commercial': (
        "Le filtre Commercial s'applique à l'onglet Commercial : commandes dont "
        "il est le vendeur, RDV dont il est l'organisateur."),
})
TOOLTIPS['ca_metier'] = (
    "CA signé par métier = CA NET de la période. Chaque commande va entière "
    "dans un métier selon ses produits principaux : Photovoltaïque (Panneaux, "
    "Onduleurs, Batteries), Chauffage / PAC (PAC, Boilers), Isolation, "
    "Autres métiers (produits directement dans All / Saleable). Services, "
    "Accessoires, Expenses, produits sans catégorie et « Frais divers » ne "
    "comptent pas. « Mixte » : commande avec plusieurs métiers. Les barres "
    "totalisent le CA NET.")


class AmssManagementDashboard(models.TransientModel):
    """AMSS Management dashboard, "Direction" tab: company-wide figures of
    the selected period. Restricted to the Direction group; the data is read
    in sudo (company-wide figures) within the user's allowed companies."""
    _name = 'amss.management.dashboard'
    _description = 'Tableau de bord AMSS Management'

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @api.model
    def _check_dashboard_access(self):
        if not (self.env.su or self.env.user.has_group(DIRECTION_GROUP)):
            raise AccessError(_("Le tableau de bord AMSS Management est réservé au groupe « Direction »."))

    @api.model
    def _allowed_company_ids(self, company_id=None):
        """Companies of the figures: the companies active in the user's
        company switcher (allowed_company_ids, sent by the dashboard), so the
        figures match the lists opened from the cards; one of them when the
        Société filter is set."""
        allowed = self.env.companies.ids
        if company_id:
            return [company_id] if company_id in allowed or self.env.su else []
        return allowed

    # ------------------------------------------------------------------
    # Periods
    # ------------------------------------------------------------------

    @api.model
    def _previous_range(self, date_start, date_end, period_type):
        """(start, end) of the previous period of the same type; for a custom
        range, the same number of days just before it. End is exclusive."""
        if period_type == 'quarter':
            return date_start - relativedelta(months=3), date_start
        if period_type == 'year':
            return date_start - relativedelta(years=1), date_start
        if period_type == 'custom':
            return date_start - (date_end - date_start), date_start
        return date_start - relativedelta(months=1), date_start

    @api.model
    def _period_short_label(self, date_start, date_end, period_type):
        if period_type == 'quarter':
            return f"T{(date_start.month - 1) // 3 + 1} {date_start.year}"
        if period_type == 'year':
            return str(date_start.year)
        if period_type == 'custom':
            last = date_end - relativedelta(days=1)
            return f"{date_start.strftime('%d/%m/%Y')} – {last.strftime('%d/%m/%Y')}"
        return MONTH_NAMES_FR[date_start.month]

    # ------------------------------------------------------------------
    # Figures
    # ------------------------------------------------------------------

    @api.model
    def _period_orders(self, date_start, date_end, company_ids, states, payment_term_id=None):
        domain = [
            ('date_order', '>=', fields.Datetime.to_string(date_start)),
            ('date_order', '<', fields.Datetime.to_string(date_end)),
            # cancelled orders: only those confirmed before (not cancelled quotes)
            *dashboard_states_domain(states),
            ('company_id', 'in', company_ids),
        ]
        if payment_term_id:
            domain.append(('payment_term_id', '=', payment_term_id))
        return self.env['sale.order'].sudo().search(domain)

    @api.model
    def _sales_figures(self, date_start, date_end, company_ids, payment_term_id=None, user_id=None):
        """CA NET, Ventes Confirmées and TX CONVERSION of a period, computed
        exactly as in Suivi Commercial (same helpers) but for every order and
        appointment of the companies. CA NET and Ventes Confirmées follow the
        payment term filter; TX CONVERSION does not (appointments have no
        payment term, so its denominator cannot be filtered)."""
        commercial = self.env['commercial.dashboard']
        all_orders = self._period_orders(date_start, date_end, company_ids, ['sale', 'done', 'cancel'])
        if user_id:
            # Commercial tab: orders of the selected salesperson
            all_orders = all_orders.filtered(lambda o: o.user_id.id == user_id)
        orders = all_orders.filtered(
            lambda o: o.payment_term_id.id == payment_term_id) if payment_term_id else all_orders
        fin = commercial._compute_financial_kpis(orders)
        fin_all = commercial._compute_financial_kpis(all_orders) if payment_term_id else fin

        events = self._appointment_events(date_start, date_end, company_ids, user_id)
        present = commercial._count_appointment_statuses(events)['attended']
        ventes_signees = fin_all['nbre_vies'] + fin_all['ventes_annulees']
        return {
            'ca_net': round(fin['ca_brut'] - fin['ca_annule'], 2),
            'ventes_confirmees': fin['nbre_vies'],
            'ventes_annulees': fin['ventes_annulees'],
            'tx_conversion': round(ventes_signees / present * 100) if present else 0,
        }

    @api.model
    def _appointment_events(self, date_start, date_end, company_ids, user_id=None):
        """Call center + commercial appointments of the period, archived
        included (as in Suivi Commercial), all statuses."""
        appointment_types = self.env['appointment.type'].sudo().search([
            ('x_appointment_ref', 'in', CALL_CENTER_APPOINTMENT_REFS + COMMERCIAL_APPOINTMENT_REFS),
        ])
        domain = [
            ('start', '>=', fields.Datetime.to_string(date_start)),
            ('start', '<', fields.Datetime.to_string(date_end)),
            ('appointment_type_id', 'in', appointment_types.ids),
            ('user_id.company_id', 'in', company_ids),
        ]
        if user_id:
            domain.append(('user_id', '=', user_id))
        return self.env['calendar.event'].sudo().with_context(active_test=False).search(domain)

    @api.model
    def _admin_projects(self, company_ids, payment_term_id=None, user_id=None):
        """Admin projects (linked to a sale order, templates excluded) of
        confirmed orders of `company_ids`, optionally of orders with the given
        payment term. The company is the order's: a project created from a
        template may have no company of its own."""
        projects = self.env['project.project'].sudo().search([
            '|',
            ('sale_line_id', '!=', False),
            ('reinvoiced_sale_order_id', '!=', False),
            ('is_template', '=', False),
        ])

        def keep(project):
            order = project._get_dossier_order()
            return (order.state == 'sale'
                    and order.company_id.id in company_ids
                    and (not payment_term_id or order.payment_term_id.id == payment_term_id)
                    and (not user_id or order.user_id.id == user_id))
        return projects.filtered(keep)

    @api.model
    def _late_projects(self, projects, today):
        """Projects with an end date and at least one open task that is due
        after that end date, or still open once the end date has passed."""
        dated = projects.filtered('date')
        tasks = self.env['project.task'].sudo().search([
            ('project_id', 'in', dated.ids),
            ('state', 'not in', ['1_done', '1_canceled']),
        ])
        local = self.with_context(tz=BGG_TZ)
        late = self.env['project.project']
        for project, open_tasks in tasks.grouped('project_id').items():
            if project.date < today or any(
                    task.date_deadline
                    and fields.Datetime.context_timestamp(local, task.date_deadline).date() > project.date
                    for task in open_tasks):
                late |= project
        return late

    @api.model
    def _blocked_projects(self, projects, cutoff=None):
        """Projects whose status is Bloqué: current status, or the status of
        the last update dated before `cutoff` (exclusive)."""
        if cutoff is None:
            return projects.filtered(lambda p: p.last_update_status == BLOCKED_STATUS)
        updates = self.env['project.update'].sudo().search([
            ('project_id', 'in', projects.ids),
            ('date', '<', cutoff),
        ], order='date desc, id desc')
        last_update = {}
        for update in updates:
            last_update.setdefault(update.project_id.id, update)
        # A Bloqué update cleared back to "no status" (x_unblocked_on) no
        # longer blocks the project from that date.
        return projects.browse([
            pid for pid, update in last_update.items()
            if update.status == BLOCKED_STATUS
            and not (update.x_unblocked_on and update.x_unblocked_on < cutoff)])

    @api.model
    def _blocked_count(self, projects, cutoff=None):
        return len(self._blocked_projects(projects, cutoff))

    @api.model
    def _cash_flow(self, date_start, date_end, company_ids, payment_term_id=None):
        """Signé / Facturé / Encaissé (HT) of the orders confirmed in the
        period. Credit notes are deducted (signed amounts); the paid part of a
        document is (total − residual) / total of its HT amount, so a credit
        note reconciled with an invoice cancels out instead of counting as
        cash."""
        orders = self._period_orders(date_start, date_end, company_ids, ['sale', 'done'],
                                     payment_term_id)
        moves = self._invoiced_moves(orders)
        signe = round(sum(orders.mapped('amount_untaxed')), 2)
        facture = round(sum(moves.mapped('amount_untaxed_signed')), 2)
        encaisse = round(sum(
            move.amount_untaxed_signed * (move.amount_total - move.amount_residual) / move.amount_total
            for move in moves if move.amount_total), 2)
        return {
            'signe': signe,
            'facture': facture,
            'encaisse': encaisse,
            # remaining parts, shown as the grey / light zones of the bars
            'reste_a_facturer': round(sum(
                max(0.0, self._not_invoiced_untaxed(order)) for order in orders), 2),
            'reste_a_encaisser': round(max(0.0, facture - encaisse), 2),
        }

    @api.model
    def _invoiced_moves(self, orders):
        """Posted customer invoices and credit notes of `orders` (Facturé)."""
        return orders.invoice_ids.filtered(
            lambda m: m.state == 'posted' and m.move_type in ('out_invoice', 'out_refund'))

    @api.model
    def _not_invoiced_untaxed(self, order):
        """HT amount of `order` not invoiced yet: line HT × (ordered −
        invoiced) / ordered, the invoiced quantities coming from the posted
        customer invoices only; an invoiced down payment not yet deducted by
        the final invoice comes off. Credit notes never put quantities back
        "to invoice": they only reduce what is owed (Reste à encaisser). An
        invoice fully cancelled by a credit note (payment status "reversed")
        counts as not invoiced."""
        total = 0.0
        for line in order.order_line:
            if line.display_type:
                continue
            invoice_lines = line.invoice_lines.filtered(
                lambda l: l.move_id.state == 'posted' and l.move_id.move_type == 'out_invoice'
                and l.move_id.payment_state != 'reversed')
            if line.is_downpayment:
                # down payment invoiced (+) and deducted by the final invoice (−)
                total -= sum(invoice_lines.mapped('price_subtotal'))
            elif line.product_uom_qty:
                invoiced = sum(invoice_lines.mapped('quantity'))
                total += line.price_subtotal * (line.product_uom_qty - invoiced) / line.product_uom_qty
        return total

    @api.model
    def _not_fully_invoiced(self, orders):
        """Orders with an HT amount left to invoice (Reste à facturer)."""
        return orders.filtered(
            lambda o: o.currency_id.compare_amounts(self._not_invoiced_untaxed(o), 0) > 0)

    @api.model
    def _not_fully_paid(self, moves):
        """Invoices and credit notes not fully paid yet (Reste à encaisser)."""
        return moves.filtered(lambda m: not m.currency_id.is_zero(m.amount_residual))

    @api.model
    def _resolve_filters(self, month=None, year=None, period_type='month', quarter=None,
                         company_id=None, date_from=None, date_to=None, payment_term_id=None,
                         user_id=None):
        date_start, date_end, period_label, month, year, quarter = \
            self.env['call.center.dashboard']._resolve_period(
                month, year, period_type, quarter, date_from, date_to)
        prev_start, prev_end = self._previous_range(date_start, date_end, period_type)
        today = fields.Date.context_today(self.with_context(tz=BGG_TZ))
        return {
            'date_start': date_start, 'date_end': date_end, 'period_label': period_label,
            'month': month, 'year': year, 'quarter': quarter, 'period_type': period_type,
            'prev_start': prev_start, 'prev_end': prev_end, 'today': today,
            # Dossiers bloqués: today for a running period, else its last day
            'blocked_cutoff': None if date_end > today else date_end,
            'company_ids': self._allowed_company_ids(company_id),
            'payment_term_id': payment_term_id,
            # Commercial tab only
            'user_id': user_id,
        }

    @api.model
    def _order_book(self, company_ids, payment_term_id=None):
        """Carnet de commandes, today: confirmed orders whose admin project is
        not Terminé, each in one row (first match): Bloqués (admin project
        Bloqué), À planifier (no admin project end date, no admin project, or
        no Responsable dossier), En cours (an admin task is done), Planifiés.
        Returns {row: sale.order recordset}."""
        Order = self.env['sale.order'].sudo()
        domain = [('state', '=', 'sale'), ('company_id', 'in', company_ids)]
        if payment_term_id:
            domain.append(('payment_term_id', '=', payment_term_id))
        orders = Order.search(domain)
        projects_by_order = {}
        for project in self._admin_projects(company_ids, payment_term_id):
            order = project._get_dossier_order()
            projects_by_order[order.id] = projects_by_order.get(order.id, project.browse()) | project
        projects = self.env['project.project'].sudo().browse(
            [p.id for ps in projects_by_order.values() for p in ps])
        started = set(self.env['project.task'].sudo().search([
            ('project_id', 'in', projects.ids), ('state', '=', '1_done'),
        ]).project_id.ids)

        rows = {row: Order.browse() for row in CARNET_ROWS}
        for order in orders:
            order_projects = projects_by_order.get(order.id, self.env['project.project'])
            if order_projects and all(p.last_update_status == 'done' for p in order_projects):
                continue  # terminé
            if any(p.last_update_status == BLOCKED_STATUS for p in order_projects):
                row = 'carnet_bloques'
            elif (not order_projects or not all(order_projects.mapped('date'))
                  or not order.x_responsable_dossier_id):
                row = 'carnet_a_planifier'
            elif set(order_projects.ids) & started:
                row = 'carnet_en_cours'
            else:
                row = 'carnet_planifies'
            rows[row] |= order
        return rows

    # ------------------------------------------------------------------
    # Recouvrement (Direction tab), à ce jour: all confirmed orders
    # ------------------------------------------------------------------

    @api.model
    def _confirmed_orders(self, company_ids, payment_term_id=None):
        """Confirmed orders of the companies, whatever their date."""
        domain = [('state', 'in', ['sale', 'done']), ('company_id', 'in', company_ids)]
        if payment_term_id:
            domain.append(('payment_term_id', '=', payment_term_id))
        return self.env['sale.order'].sudo().search(domain)

    @api.model
    def _unpaid_untaxed(self, moves):
        """Unpaid part (HT) of invoices / credit notes, credit notes deducted:
        HT × residual / total (the complement of Encaissé)."""
        return sum(
            move.amount_untaxed_signed * move.amount_residual / move.amount_total
            for move in moves if move.amount_total)

    @api.model
    def _sss_projects_by_order(self, orders):
        """{order id: field service (SSS) projects} for `orders`. The SSS
        project is created by the "Créer tâches SSS" server action (Studio):
        a field service project linked to the order (sale_order_id) and named
        "<order> - SSS - <client>"."""
        Project = self.env['project.project'].sudo()
        if 'is_fsm' not in Project._fields or not orders:
            return {}
        by_name = {order.name: order.id for order in orders}
        projects = Project.search([('is_fsm', '=', True), ('is_template', '=', False)])
        result = {}
        for project in projects:
            order_id = (project.sale_order_id.id if 'sale_order_id' in Project._fields else False)
            if order_id not in orders.ids:
                order_id = by_name.get((project.name or '').split(' - SSS - ')[0].strip())
            if order_id:
                result[order_id] = result.get(order_id, Project.browse()) | project
        return result

    @api.model
    def _sss_finished_orders(self, orders):
        """Orders whose SSS project(s) have all their tasks closed (done or
        cancelled), at least one done."""
        sss = self._sss_projects_by_order(orders)
        if not sss:
            return orders.browse()
        projects = self.env['project.project'].sudo().browse(
            [p.id for ps in sss.values() for p in ps])
        tasks_by_project = self.env['project.task'].sudo().search(
            [('project_id', 'in', projects.ids)]).grouped('project_id')

        def finished(project):
            tasks = tasks_by_project.get(project, self.env['project.task'])
            return (tasks and all(t.state in ('1_done', '1_canceled') for t in tasks)
                    and any(t.state == '1_done' for t in tasks))
        return orders.filtered(lambda o: o.id in sss and all(finished(p) for p in sss[o.id]))

    @api.model
    def _recouvrement(self, company_ids, payment_term_id=None):
        """Reste à facturer / Reste à encaisser / Reste à encaisser des
        chantiers SSS terminés, à ce jour. Returns {key: (records, amount)}."""
        orders = self._confirmed_orders(company_ids, payment_term_id)
        moves = self._invoiced_moves(orders)
        rounding = self.env.company.currency_id

        not_invoiced = {order.id: max(0.0, self._not_invoiced_untaxed(order)) for order in orders}
        to_invoice = orders.filtered(lambda o: rounding.compare_amounts(not_invoiced[o.id], 0) > 0)
        to_invoice_amount = sum(not_invoiced[o.id] for o in to_invoice)

        unpaid = self._not_fully_paid(moves)
        unpaid_amount = self._unpaid_untaxed(unpaid)

        # still owed on the order: not invoiced yet + unpaid part of its
        # invoices / credit notes
        sss_due, sss_amount = orders.browse(), 0.0
        for order in self._sss_finished_orders(orders):
            gap = not_invoiced[order.id] + self._unpaid_untaxed(self._invoiced_moves(order))
            if rounding.compare_amounts(gap, 0) > 0:
                sss_due |= order
                sss_amount += gap
        return {
            'recouvrement_facturer': (to_invoice, round(to_invoice_amount, 2)),
            'recouvrement_encaisser': (unpaid, round(unpaid_amount, 2)),
            'recouvrement_sss': (sss_due, round(sss_amount, 2)),
        }

    @api.model
    def _recouvrement_figures(self, company_ids, payment_term_id=None):
        return {key: {'amount': amount, 'count': len(records)}
                for key, (records, amount) in self._recouvrement(company_ids, payment_term_id).items()}

    @api.model
    def _order_book_figures(self, company_ids, payment_term_id=None):
        rows = self._order_book(company_ids, payment_term_id)
        total = self.env['sale.order'].sudo().browse()
        for orders in rows.values():
            total |= orders
        figures = {row: len(orders) for row, orders in rows.items()}
        figures.update({
            'carnet_total': len(total),
            'carnet_total_amount': round(sum(total.mapped('amount_untaxed')), 2),
        })
        return figures

    @api.model
    def _category_metier(self, categ):
        """Métier of a product category, from its first level under
        All / Saleable (METIER_BY_CATEGORY, else the sub-category name);
        Autres métiers for All / Saleable itself, Aucun / Autres otherwise."""
        if not categ:
            return METIER_NONE
        parts = tuple(part.strip() for part in (categ.complete_name or '').split('/'))
        if parts[:len(SALEABLE_PATH)] != SALEABLE_PATH:
            return METIER_OTHER
        if len(parts) == len(SALEABLE_PATH):
            return METIER_SALEABLE
        sub = parts[len(SALEABLE_PATH)]
        return METIER_BY_CATEGORY.get(sub, sub)

    @api.model
    def _order_metier(self, order):
        """Métier of an order: the métier of its main products, Mixte if
        several. Services / Accessoires / Aucun / Autres only decide when the
        order has no main product; "Frais divers" never does."""
        main, minor = set(), set()
        for line in order.order_line:
            if line.display_type or not line.product_id or line.is_downpayment:
                continue
            if line.product_id.default_code in METIER_IGNORED_PRODUCT_CODES:
                continue
            metier = self._category_metier(line.product_id.categ_id)
            (minor if metier in METIER_MINOR else main).add(metier)
        found = main or minor
        if not found:
            return METIER_NONE
        return found.pop() if len(found) == 1 else METIER_MIXED

    @api.model
    def _group_by_metier(self, orders):
        result = {}
        for order in orders:
            metier = self._order_metier(order)
            result[metier] = result.get(metier, order.browse()) | order
        return result

    @api.model
    def _orders_by_metier(self, f):
        """{métier: confirmed orders of the period} (the CA NET orders)."""
        return self._group_by_metier(self._period_orders(
            f['date_start'], f['date_end'], f['company_ids'], ['sale', 'done'], f['payment_term_id']))

    # ------------------------------------------------------------------
    # Commercial tab
    # ------------------------------------------------------------------

    @api.model
    def _commercial_users(self):
        group = self.env.ref(COMMERCIAL_GROUP, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        return group.sudo().user_ids.filtered('active').sorted('name')

    @api.model
    def _commercial_orders(self, f, states, by_user=True):
        """Orders of the period (filters), of the selected salesperson."""
        orders = self._period_orders(f['date_start'], f['date_end'], f['company_ids'],
                                     states, f['payment_term_id'])
        if by_user and f.get('user_id'):
            orders = orders.filtered(lambda o: o.user_id.id == f['user_id'])
        return orders

    @api.model
    def _commercial_events(self, f):
        """Call center + commercial appointments of the period (archived
        included, as in Suivi Commercial), of the selected salesperson."""
        types = self.env['appointment.type'].sudo().search([
            ('x_appointment_ref', 'in', CALL_CENTER_APPOINTMENT_REFS + COMMERCIAL_APPOINTMENT_REFS),
        ])
        domain = [
            ('start', '>=', fields.Datetime.to_string(f['date_start'])),
            ('start', '<', fields.Datetime.to_string(f['date_end'])),
            ('appointment_type_id', 'in', types.ids),
            ('user_id.company_id', 'in', f['company_ids']),
            ('appointment_status', 'in', ['attended', 'no_show', 'cancelled', 'booked']),
        ]
        if f.get('user_id'):
            domain.append(('user_id', '=', f['user_id']))
        return self.env['calendar.event'].sudo().with_context(active_test=False).search(domain)

    @api.model
    def _commercial_bc_groups(self, f):
        """{salesperson id (str) or 'autres': confirmed orders of the period}
        for every salesperson (the bars are not limited by the filter)."""
        users = set(self._commercial_users().ids)
        groups = {}
        for order in self._commercial_orders(f, ['sale', 'done'], by_user=False):
            key = str(order.user_id.id) if order.user_id.id in users else OTHER_SALESPEOPLE
            groups[key] = groups.get(key, order.browse()) | order
        return groups

    @api.model
    def _commercial_figures(self, f):
        users = self._commercial_users()
        groups = self._commercial_bc_groups(f)
        selected = str(f['user_id']) if f.get('user_id') else None
        bars = [{'key': str(u.id), 'label': u.name, 'count': len(groups.get(str(u.id), []))}
                for u in users if groups.get(str(u.id)) or str(u.id) == selected]
        bars.sort(key=lambda b: (-b['count'], b['label']))
        if groups.get(OTHER_SALESPEOPLE):
            bars.append({'key': OTHER_SALESPEOPLE, 'label': 'Autres',
                         'count': len(groups[OTHER_SALESPEOPLE])})

        confirmed = self._commercial_orders(f, ['sale', 'done'])
        cancelled = self._commercial_orders(f, ['cancel'])
        events = self._commercial_events(f)
        signed = len(confirmed) + len(cancelled)
        metiers = []
        for metier, orders in self._group_by_metier(confirmed).items():
            metiers.append({'key': metier, 'label': metier, 'count': len(orders),
                            'panier': round(sum(orders.mapped('amount_untaxed')) / len(orders), 2)})
        metiers.sort(key=lambda m: (-m['count'], m['label']))
        return {
            'selected_user_id': f.get('user_id') or False,
            'bc_par_commercial': bars,
            'funnel': {
                'rdv_poses': len(events),
                'rdv_tenus': len(events.filtered(lambda e: e.appointment_status == 'attended')),
                'bc_signes': signed,
            },
            'qualite': {
                'panier_moyen': round(sum(confirmed.mapped('amount_untaxed')) / len(confirmed), 2)
                if confirmed else 0,
                'panier_par_metier': metiers,
                'annulation_signature': round(len(cancelled) / signed * 100, 1) if signed else 0,
            },
        }

    @api.model
    def _ca_by_metier(self, f):
        """[{'key', 'label', 'amount'}] sorted by amount, largest first."""
        rows = [{'key': metier, 'label': metier,
                 'amount': round(sum(orders.mapped('amount_untaxed')), 2)}
                for metier, orders in self._orders_by_metier(f).items()]
        return sorted(rows, key=lambda r: (-r['amount'], r['label']))

    @api.model
    def _card_records(self, card, f):
        """Records behind a card or a bar (the ones its figure is computed
        from), for the resolved filters `f`."""
        if card == 'ventes_annulees':
            orders = self._period_orders(f['date_start'], f['date_end'], f['company_ids'],
                                         ['cancel'], f['payment_term_id'])
            if f.get('user_id'):
                orders = orders.filtered(lambda o: o.user_id.id == f['user_id'])
            return orders
        if card == 'tx_conversion':
            # the denominator: RDV Présents
            return self._appointment_events(
                f['date_start'], f['date_end'], f['company_ids'], f.get('user_id'),
            ).filtered(lambda e: e.appointment_status == 'attended')
        if card in ('ca_net', 'ventes_confirmees', 'signe', 'facture', 'encaisse',
                    'reste_a_facturer', 'reste_a_encaisser'):
            orders = self._period_orders(f['date_start'], f['date_end'], f['company_ids'],
                                         ['sale', 'done'], f['payment_term_id'])
            if f.get('user_id') and card in ('ca_net', 'ventes_confirmees'):
                orders = orders.filtered(lambda o: o.user_id.id == f['user_id'])
            if card == 'facture':
                return self._invoiced_moves(orders)
            if card == 'encaisse':
                return self._invoiced_moves(orders).filtered(
                    lambda m: m.amount_total and m.amount_residual < m.amount_total)
            if card == 'reste_a_facturer':
                return self._not_fully_invoiced(orders)
            if card == 'reste_a_encaisser':
                return self._not_fully_paid(self._invoiced_moves(orders))
            return orders
        if card.startswith('metier:'):
            return self._orders_by_metier(f).get(card[len('metier:'):], self.env['sale.order'])
        if card.startswith('commercial_bc:'):
            return self._commercial_bc_groups(f).get(card[len('commercial_bc:'):], self.env['sale.order'])
        if card.startswith('panier_metier:'):
            return self._group_by_metier(self._commercial_orders(f, ['sale', 'done'])).get(
                card[len('panier_metier:'):], self.env['sale.order'])
        if card == 'funnel_bc':
            return self._commercial_orders(f, ['sale', 'done', 'cancel'])
        if card in ('funnel_rdv_poses', 'funnel_rdv_tenus'):
            events = self._commercial_events(f)
            if card == 'funnel_rdv_tenus':
                events = events.filtered(lambda e: e.appointment_status == 'attended')
            return events
        if card.startswith('recouvrement_'):
            return self._recouvrement(f['company_ids'], f['payment_term_id'])[card][0]
        if card in CARNET_ROWS or card == 'carnet_total':
            rows = self._order_book(f['company_ids'], f['payment_term_id'])
            if card in rows:
                return rows[card]
            total = self.env['sale.order'].sudo().browse()
            for orders in rows.values():
                total |= orders
            return total
        projects = self._admin_projects(f['company_ids'], f['payment_term_id'], f.get('user_id'))
        if card == 'chantiers_retard':
            return self._late_projects(projects, f['today'])
        if card == 'dossiers_bloques':
            return self._blocked_projects(projects, f['blocked_cutoff'])
        raise ValueError("Unknown card %r" % card)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @api.model
    def get_filter_options(self):
        self._check_dashboard_access()
        companies = self.env.companies.sorted('name')
        terms = self.env['account.payment.term'].sudo().search([
            ('company_id', 'in', companies.ids + [False]),
        ], order='name')
        return {
            'companies': [{'id': c.id, 'name': c.name} for c in companies],
            'payment_terms': [{'id': t.id, 'name': t.name} for t in terms],
            'salespeople': [{'id': u.id, 'name': u.name} for u in self._commercial_users()],
        }

    @api.model
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, company_id=None, date_from=None, date_to=None,
                           payment_term_id=None, user_id=None):
        self._check_dashboard_access()
        f = self._resolve_filters(month, year, period_type, quarter, company_id,
                                  date_from, date_to, payment_term_id, user_id)
        date_start, date_end, prev_start, prev_end = (
            f['date_start'], f['date_end'], f['prev_start'], f['prev_end'])
        company_ids, today = f['company_ids'], f['today']
        month, year, quarter, period_label = f['month'], f['year'], f['quarter'], f['period_label']

        company = self.env['res.company'].browse(company_ids[:1]) if company_ids else self.env.company
        return {
            'period_label': period_label,
            'previous_label': self._period_short_label(prev_start, prev_end, period_type),
            'current_month': month,
            'current_year': year,
            'current_quarter': quarter,
            'currency': {
                'symbol': company.currency_id.symbol,
                'position': company.currency_id.position,
                'decimal_places': company.currency_id.decimal_places,
            },
            'tooltips': TOOLTIPS,
            'payment_term_filtered': bool(payment_term_id),
            'blocked_as_of': (False if f['blocked_cutoff'] is None else
                              (date_end - relativedelta(days=1)).strftime('%d/%m/%Y')),
            'cards': self._kpi_cards(f),
            # Commercial tab: the same cards for the selected salesperson
            'cards_user': self._kpi_cards(f, user_id) if user_id else False,
            'cash_flow': self._cash_flow(date_start, date_end, company_ids, payment_term_id),
            'order_book': self._order_book_figures(company_ids, payment_term_id),
            'recouvrement': self._recouvrement_figures(company_ids, payment_term_id),
            'metiers': {'ca_par_metier': self._ca_by_metier(f)},
            'commercial': self._commercial_figures(f),
        }

    @api.model
    def _kpi_cards(self, f, user_id=None):
        """The KPI cards shown on top of every tab: company-wide, or for the
        orders / appointments of one salesperson (Commercial tab)."""
        current = self._sales_figures(f['date_start'], f['date_end'], f['company_ids'],
                                      f['payment_term_id'], user_id)
        previous = self._sales_figures(f['prev_start'], f['prev_end'], f['company_ids'],
                                       f['payment_term_id'], user_id)
        projects = self._admin_projects(f['company_ids'], f['payment_term_id'], user_id)
        blocked_now = self._blocked_count(projects, f['blocked_cutoff'])
        blocked_prev = self._blocked_count(projects, f['date_start'])

        def delta(key, kind):
            cur, prev = current[key], previous[key]
            if kind == 'pct':
                return round((cur - prev) / prev * 100) if prev else None
            return cur - prev

        return {
            'ca_net': {'value': current['ca_net'], 'previous': previous['ca_net'],
                       'delta': delta('ca_net', 'pct')},
            'ventes_confirmees': {'value': current['ventes_confirmees'],
                                  'previous': previous['ventes_confirmees'],
                                  'delta': delta('ventes_confirmees', 'count')},
            # secondary figure of the Ventes Confirmées card
            'ventes_annulees': {'value': current['ventes_annulees'],
                                'previous': previous['ventes_annulees'],
                                'delta': delta('ventes_annulees', 'count')},
            'tx_conversion': {'value': current['tx_conversion'],
                              'previous': previous['tx_conversion'],
                              'delta': delta('tx_conversion', 'points')},
            'chantiers_retard': {'value': len(self._late_projects(projects, f['today']))},
            'dossiers_bloques': {'value': blocked_now, 'previous': blocked_prev,
                                 'delta': blocked_now - blocked_prev},
        }

    @api.model
    def open_card(self, card, month=None, year=None, period_type='month', quarter=None,
                  company_id=None, date_from=None, date_to=None, payment_term_id=None,
                  user_id=None):
        """Window action listing the records behind a card, with the same
        filters. The list opens with the user's own access rights."""
        self._check_dashboard_access()
        f = self._resolve_filters(month, year, period_type, quarter, company_id,
                                  date_from, date_to, payment_term_id, user_id)
        records = self._card_records(card, f)
        titles = {
            'ca_net': 'CA NET', 'ventes_confirmees': 'Ventes confirmées',
            'ventes_annulees': 'Ventes annulées', 'tx_conversion': 'TX CONVERSION – RDV présents',
            'signe': 'Signé',
            'facture': 'Facturé', 'encaisse': 'Encaissé',
            'reste_a_facturer': 'Reste à facturer', 'reste_a_encaisser': 'Reste à encaisser',
            'recouvrement_facturer': 'Reste à facturer',
            'recouvrement_encaisser': 'Reste à encaisser',
            'recouvrement_sss': 'Reste à encaisser – chantiers SSS terminés',
            'chantiers_retard': 'Chantiers en retard', 'dossiers_bloques': 'Dossiers bloqués',
            'carnet_a_planifier': 'Carnet de commandes – À planifier',
            'carnet_planifies': 'Carnet de commandes – Planifiés',
            'carnet_en_cours': 'Carnet de commandes – En cours',
            'carnet_bloques': 'Carnet de commandes – Bloqués',
            'carnet_total': 'Carnet de commandes – BC signés non terminés',
        }
        if card.startswith('metier:'):
            titles[card] = 'CA signé – %s' % card[len('metier:'):]
        if card.startswith('panier_metier:'):
            titles[card] = 'Panier moyen – %s' % card[len('panier_metier:'):]
        if card.startswith('commercial_bc:'):
            key = card[len('commercial_bc:'):]
            titles[card] = 'BC signés – %s' % (
                'Autres' if key == OTHER_SALESPEOPLE else self.env['res.users'].sudo().browse(int(key)).name)
        titles.update({'funnel_rdv_poses': 'RDV posés', 'funnel_rdv_tenus': 'RDV tenus',
                       'funnel_bc': 'BC signés (confirmés + annulés)'})
        if f.get('user_id') and (card.startswith(('panier_metier:', 'funnel_'))):
            titles[card] += ' (%s)' % self.env['res.users'].sudo().browse(f['user_id']).name
        suffix = ('à ce jour' if card == 'chantiers_retard'
                  or card.startswith(('carnet_', 'recouvrement_'))
                  or (card == 'dossiers_bloques' and f['blocked_cutoff'] is None)
                  else f['period_label'])
        return {
            'type': 'ir.actions.act_window',
            'name': '%s – %s' % (titles[card], suffix),
            'res_model': records._name,
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('id', 'in', records.ids)],
            # appointments include archived ones (as in Suivi Commercial)
            'context': {'create': False, 'active_test': records._name != 'calendar.event'},
            'target': 'current',
        }

    @api.model
    def export_excel(self, month=None, year=None, period_type='month',
                     quarter=None, company_id=None, date_from=None, date_to=None,
                     payment_term_id=None, user_id=None):
        """Excel file (base64): the Direction figures and a Calculs sheet."""
        import xlsxwriter

        data = self.get_dashboard_data(
            month=month, year=year, period_type=period_type, quarter=quarter,
            company_id=company_id, date_from=date_from, date_to=date_to,
            payment_term_id=payment_term_id, user_id=user_id)
        cards, cash = data['cards'], data['cash_flow']

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        base = {'font_name': 'Arial', 'font_size': 10, 'border': 1}
        header_fmt = workbook.add_format(dict(base, bold=True, bg_color='#2c3e50',
                                              font_color='white', align='center'))
        label_fmt = workbook.add_format(dict(base, bold=True, bg_color='#f8f9fa'))
        cell_fmt = workbook.add_format(dict(base, align='center'))
        money_fmt = workbook.add_format(dict(base, align='center', num_format='#,##0.00 €'))
        pct_fmt = workbook.add_format(dict(base, align='center', num_format='0%'))
        wrap_fmt = workbook.add_format(dict(base, text_wrap=True, valign='top'))

        sheet = workbook.add_worksheet('Direction')
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 3, 18)
        sheet.write_row(0, 0, [data['period_label'], 'Valeur',
                               'Période précédente (%s)' % data['previous_label'], 'Écart'],
                        header_fmt)
        rows = [
            ('CA NET', cards['ca_net'], money_fmt, 'pct'),
            ('VENTES CONFIRMÉES', cards['ventes_confirmees'], cell_fmt, 'count'),
            ('VENTES ANNULÉES', cards['ventes_annulees'], cell_fmt, 'count'),
            ('TX CONVERSION (toutes conditions)' if data['payment_term_filtered'] else 'TX CONVERSION',
             cards['tx_conversion'], pct_fmt, 'points'),
            ('CHANTIERS EN RETARD', cards['chantiers_retard'], cell_fmt, None),
            ('DOSSIERS BLOQUÉS', cards['dossiers_bloques'], cell_fmt, 'count'),
        ]
        row = 1
        for label, card, fmt, kind in rows:
            scale = 100.0 if fmt is pct_fmt else 1
            sheet.write(row, 0, label, label_fmt)
            sheet.write_number(row, 1, card['value'] / scale, fmt)
            if kind:
                sheet.write_number(row, 2, card['previous'] / scale, fmt)
                if card['delta'] is None:
                    sheet.write(row, 3, '', cell_fmt)
                elif kind == 'pct':
                    sheet.write(row, 3, '%+d %%' % card['delta'], cell_fmt)
                elif kind == 'points':
                    sheet.write(row, 3, '%+d pts' % card['delta'], cell_fmt)
                else:
                    sheet.write(row, 3, '%+d' % card['delta'], cell_fmt)
            else:
                sheet.write(row, 2, 'à ce jour', cell_fmt)
                sheet.write(row, 3, '', cell_fmt)
            row += 1
        row += 1
        sheet.write(row, 0, 'CA SIGNÉ / FACTURÉ / ENCAISSÉ', header_fmt)
        sheet.write(row, 1, 'Montant HT', header_fmt)
        for label, key in (('Signé', 'signe'), ('Facturé', 'facture'), ('Encaissé', 'encaisse'),
                           ('Reste à facturer', 'reste_a_facturer'),
                           ('Reste à encaisser', 'reste_a_encaisser')):
            row += 1
            sheet.write(row, 0, label, label_fmt)
            sheet.write_number(row, 1, cash[key], money_fmt)

        recouvrement = data['recouvrement']
        row += 2
        sheet.write(row, 0, 'RECOUVREMENT (à ce jour)', header_fmt)
        sheet.write(row, 1, 'Montant HT', header_fmt)
        sheet.write(row, 2, 'Nombre', header_fmt)
        for label, key in (('Reste à facturer', 'recouvrement_facturer'),
                           ('Reste à encaisser', 'recouvrement_encaisser'),
                           ('Reste à encaisser – chantiers SSS terminés', 'recouvrement_sss')):
            row += 1
            sheet.write(row, 0, label, label_fmt)
            sheet.write_number(row, 1, recouvrement[key]['amount'], money_fmt)
            sheet.write_number(row, 2, recouvrement[key]['count'], cell_fmt)

        book = data['order_book']
        row += 2
        sheet.write(row, 0, 'CARNET DE COMMANDES (à ce jour)', header_fmt)
        sheet.write(row, 1, 'Commandes', header_fmt)
        for label, key in (('À planifier', 'carnet_a_planifier'), ('Planifiés', 'carnet_planifies'),
                           ('En cours', 'carnet_en_cours'), ('Bloqués', 'carnet_bloques')):
            row += 1
            sheet.write(row, 0, label, label_fmt)
            sheet.write_number(row, 1, book[key], cell_fmt)
        row += 1
        sheet.write(row, 0, 'BC signés non terminés', label_fmt)
        sheet.write_number(row, 1, book['carnet_total'], cell_fmt)
        sheet.write_number(row, 2, book['carnet_total_amount'], money_fmt)

        metiers = workbook.add_worksheet('Métiers')
        metiers.set_column(0, 0, 30)
        metiers.set_column(1, 1, 18)
        metiers.write_row(0, 0, ['CA SIGNÉ PAR MÉTIER – %s' % data['period_label'], 'Montant HT'],
                          header_fmt)
        for i, item in enumerate(data['metiers']['ca_par_metier'], start=1):
            metiers.write(i, 0, item['label'], label_fmt)
            metiers.write_number(i, 1, item['amount'], money_fmt)

        com = data['commercial']
        com_sheet = workbook.add_worksheet('Commercial')
        com_sheet.set_column(0, 0, 34)
        com_sheet.set_column(1, 1, 18)
        title = 'COMMERCIAL – %s' % data['period_label']
        if com['selected_user_id']:
            title += ' – %s' % self.env['res.users'].sudo().browse(com['selected_user_id']).name
        com_sheet.write_row(0, 0, [title, ''], header_fmt)
        r = 1
        com_sheet.write_row(r, 0, ['BC SIGNÉS PAR COMMERCIAL', 'BC'], header_fmt)
        for bar in com['bc_par_commercial']:
            r += 1
            com_sheet.write(r, 0, bar['label'], label_fmt)
            com_sheet.write_number(r, 1, bar['count'], cell_fmt)
        r += 2
        com_sheet.write_row(r, 0, ['ENTONNOIR DE CONVERSION', ''], header_fmt)
        for label, key in (('RDV posés', 'rdv_poses'), ('RDV tenus', 'rdv_tenus'),
                           ('BC signés (confirmés + annulés)', 'bc_signes')):
            r += 1
            com_sheet.write(r, 0, label, label_fmt)
            com_sheet.write_number(r, 1, com['funnel'][key], cell_fmt)
        r += 2
        com_sheet.write_row(r, 0, ['QUALITÉ COMMERCIALE', 'Valeur'], header_fmt)
        r += 1
        com_sheet.write(r, 0, 'Panier moyen (tous métiers)', label_fmt)
        com_sheet.write_number(r, 1, com['qualite']['panier_moyen'], money_fmt)
        for item in com['qualite']['panier_par_metier']:
            r += 1
            com_sheet.write(r, 0, 'Panier moyen %s' % item['label'], label_fmt)
            com_sheet.write_number(r, 1, item['panier'], money_fmt)
        r += 1
        com_sheet.write(r, 0, 'Annulation après signature', label_fmt)
        com_sheet.write_number(r, 1, com['qualite']['annulation_signature'] / 100.0, pct_fmt)

        calc = workbook.add_worksheet('Calculs')
        calc.set_column(0, 0, 26)
        calc.set_column(1, 1, 90)
        calc.write_row(0, 0, ['Champ', 'Formule / description'], header_fmt)
        for i, (label, key) in enumerate((
                ('CA NET', 'ca_net'), ('VENTES CONFIRMÉES', 'ventes_confirmees'),
                ('VENTES ANNULÉES', 'ventes_annulees'),
                ('TX CONVERSION', 'tx_conversion'), ('CHANTIERS EN RETARD', 'chantiers_retard'),
                ('DOSSIERS BLOQUÉS', 'dossiers_bloques'), ('SIGNÉ', 'signe'),
                ('FACTURÉ', 'facture'), ('ENCAISSÉ', 'encaisse'),
                ('RESTE À FACTURER', 'reste_a_facturer'), ('RESTE À ENCAISSER', 'reste_a_encaisser'),
                ('RESTE À FACTURER (À CE JOUR)', 'recouvrement_facturer'),
                ('RESTE À ENCAISSER (À CE JOUR)', 'recouvrement_encaisser'),
                ('RESTE À ENCAISSER – CHANTIERS SSS TERMINÉS', 'recouvrement_sss'),
                ('CARNET – BLOQUÉS', 'carnet_bloques'), ('CARNET – À PLANIFIER', 'carnet_a_planifier'),
                ('CARNET – EN COURS', 'carnet_en_cours'), ('CARNET – PLANIFIÉS', 'carnet_planifies'),
                ('CARNET DE COMMANDES', 'carnet_total'),
                ('CA SIGNÉ PAR MÉTIER', 'ca_metier'),
                ('BC SIGNÉS PAR COMMERCIAL', 'bc_par_commercial'), ('RDV POSÉS', 'funnel_rdv_poses'),
                ('RDV TENUS', 'funnel_rdv_tenus'), ('BC SIGNÉS (ENTONNOIR)', 'funnel_bc'),
                ('PANIER MOYEN', 'panier_moyen'), ('PANIER MOYEN PAR MÉTIER', 'panier_metier'),
                ('ANNULATION APRÈS SIGNATURE', 'annulation_signature'),
                ('FILTRE COMMERCIAL', 'filtre_commercial')), start=1):
            calc.write(i, 0, label, label_fmt)
            calc.write(i, 1, TOOLTIPS[key], wrap_fmt)
            calc.set_row(i, 42)
        calc.write(len(TOOLTIPS) + 2, 0, 'Comparaison', label_fmt)
        calc.write(len(TOOLTIPS) + 2, 1, (
            "Période précédente du même type (mois, trimestre, année ; pour une "
            "période personnalisée, le même nombre de jours juste avant). Toutes "
            "les commandes et tous les RDV des sociétés sélectionnées sont pris en "
            "compte (pas seulement le groupe Commercial). Le filtre condition de "
            "paiement s'applique à toutes les valeurs sauf TX CONVERSION."), wrap_fmt)

        workbook.close()
        return base64.b64encode(output.getvalue()).decode('utf-8')
