# -*- coding: utf-8 -*-

import base64
import io
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .commercial_dashboard import CALL_CENTER_APPOINTMENT_REFS, COMMERCIAL_APPOINTMENT_REFS
from .project_update import BLOCKED_STATUS
from .sale_order import BGG_TZ

_logger = logging.getLogger(__name__)

DIRECTION_GROUP = 'bgg_custom_dev.group_direction'

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
        "condition de paiement : les RDV n'ont pas de condition de paiement."),
    'chantiers_retard': (
        "Chantiers en retard = projets admin (commandes confirmées) ayant au "
        "moins une tâche ouverte dont l'échéance dépasse la date de fin du "
        "projet, ou encore ouverte après cette date. Situation à ce jour."),
    'dossiers_bloques': (
        "Dossiers bloqués = projets admin dont le dernier statut est « Bloqué » "
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
}


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
        allowed = self.env.user.company_ids.ids
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
            ('state', 'in', states),
            ('company_id', 'in', company_ids),
        ]
        if payment_term_id:
            domain.append(('payment_term_id', '=', payment_term_id))
        return self.env['sale.order'].sudo().search(domain)

    @api.model
    def _sales_figures(self, date_start, date_end, company_ids, payment_term_id=None):
        """CA NET, Ventes Confirmées and TX CONVERSION of a period, computed
        exactly as in Suivi Commercial (same helpers) but for every order and
        appointment of the companies. CA NET and Ventes Confirmées follow the
        payment term filter; TX CONVERSION does not (appointments have no
        payment term, so its denominator cannot be filtered)."""
        commercial = self.env['commercial.dashboard']
        all_orders = self._period_orders(date_start, date_end, company_ids, ['sale', 'done', 'cancel'])
        orders = all_orders.filtered(
            lambda o: o.payment_term_id.id == payment_term_id) if payment_term_id else all_orders
        fin = commercial._compute_financial_kpis(orders)
        fin_all = commercial._compute_financial_kpis(all_orders) if payment_term_id else fin

        appointment_types = self.env['appointment.type'].sudo().search([
            ('x_appointment_ref', 'in', CALL_CENTER_APPOINTMENT_REFS + COMMERCIAL_APPOINTMENT_REFS),
        ])
        events = self.env['calendar.event'].sudo().with_context(active_test=False).search([
            ('start', '>=', fields.Datetime.to_string(date_start)),
            ('start', '<', fields.Datetime.to_string(date_end)),
            ('appointment_type_id', 'in', appointment_types.ids),
            ('user_id.company_id', 'in', company_ids),
        ])
        present = commercial._count_appointment_statuses(events)['attended']
        ventes_signees = fin_all['nbre_vies'] + fin_all['ventes_annulees']
        return {
            'ca_net': round(fin['ca_brut'] - fin['ca_annule'], 2),
            'ventes_confirmees': fin['nbre_vies'],
            'tx_conversion': round(ventes_signees / present * 100) if present else 0,
        }

    @api.model
    def _admin_projects(self, company_ids, payment_term_id=None):
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
                    and (not payment_term_id or order.payment_term_id.id == payment_term_id))
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
        last_status = {}
        for update in updates:
            last_status.setdefault(update.project_id.id, update.status)
        return projects.browse([pid for pid, status in last_status.items() if status == BLOCKED_STATUS])

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
        facture = sum(moves.mapped('amount_untaxed_signed'))
        encaisse = sum(
            move.amount_untaxed_signed * (move.amount_total - move.amount_residual) / move.amount_total
            for move in moves if move.amount_total)
        return {
            'signe': round(sum(orders.mapped('amount_untaxed')), 2),
            'facture': round(facture, 2),
            'encaisse': round(encaisse, 2),
        }

    @api.model
    def _invoiced_moves(self, orders):
        """Posted customer invoices and credit notes of `orders` (Facturé)."""
        return orders.invoice_ids.filtered(
            lambda m: m.state == 'posted' and m.move_type in ('out_invoice', 'out_refund'))

    @api.model
    def _resolve_filters(self, month=None, year=None, period_type='month', quarter=None,
                         company_id=None, date_from=None, date_to=None, payment_term_id=None):
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
        }

    @api.model
    def _card_records(self, card, f):
        """Records behind a card or a bar (the ones its figure is computed
        from), for the resolved filters `f`."""
        if card in ('ca_net', 'ventes_confirmees', 'signe', 'facture', 'encaisse'):
            orders = self._period_orders(f['date_start'], f['date_end'], f['company_ids'],
                                         ['sale', 'done'], f['payment_term_id'])
            if card == 'facture':
                return self._invoiced_moves(orders)
            if card == 'encaisse':
                return self._invoiced_moves(orders).filtered(
                    lambda m: m.amount_total and m.amount_residual < m.amount_total)
            return orders
        projects = self._admin_projects(f['company_ids'], f['payment_term_id'])
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
        companies = self.env.user.company_ids.sorted('name')
        terms = self.env['account.payment.term'].sudo().search([
            ('company_id', 'in', companies.ids + [False]),
        ], order='name')
        return {
            'companies': [{'id': c.id, 'name': c.name} for c in companies],
            'payment_terms': [{'id': t.id, 'name': t.name} for t in terms],
        }

    @api.model
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, company_id=None, date_from=None, date_to=None,
                           payment_term_id=None):
        self._check_dashboard_access()
        f = self._resolve_filters(month, year, period_type, quarter, company_id,
                                  date_from, date_to, payment_term_id)
        date_start, date_end, prev_start, prev_end = (
            f['date_start'], f['date_end'], f['prev_start'], f['prev_end'])
        company_ids, today = f['company_ids'], f['today']
        month, year, quarter, period_label = f['month'], f['year'], f['quarter'], f['period_label']

        current = self._sales_figures(date_start, date_end, company_ids, payment_term_id)
        previous = self._sales_figures(prev_start, prev_end, company_ids, payment_term_id)

        projects = self._admin_projects(company_ids, payment_term_id)
        blocked_now = self._blocked_count(projects, f['blocked_cutoff'])
        blocked_prev = self._blocked_count(projects, date_start)

        def delta(key, kind):
            cur, prev = current[key], previous[key]
            if kind == 'pct':
                return round((cur - prev) / prev * 100) if prev else None
            return cur - prev

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
            'cards': {
                'ca_net': {'value': current['ca_net'], 'previous': previous['ca_net'],
                           'delta': delta('ca_net', 'pct')},
                'ventes_confirmees': {'value': current['ventes_confirmees'],
                                      'previous': previous['ventes_confirmees'],
                                      'delta': delta('ventes_confirmees', 'count')},
                'tx_conversion': {'value': current['tx_conversion'],
                                  'previous': previous['tx_conversion'],
                                  'delta': delta('tx_conversion', 'points')},
                'chantiers_retard': {'value': len(self._late_projects(projects, today))},
                'dossiers_bloques': {'value': blocked_now, 'previous': blocked_prev,
                                     'delta': blocked_now - blocked_prev},
            },
            'cash_flow': self._cash_flow(date_start, date_end, company_ids, payment_term_id),
        }

    @api.model
    def open_card(self, card, month=None, year=None, period_type='month', quarter=None,
                  company_id=None, date_from=None, date_to=None, payment_term_id=None):
        """Window action listing the records behind a card, with the same
        filters. The list opens with the user's own access rights."""
        self._check_dashboard_access()
        f = self._resolve_filters(month, year, period_type, quarter, company_id,
                                  date_from, date_to, payment_term_id)
        records = self._card_records(card, f)
        titles = {
            'ca_net': 'CA NET', 'ventes_confirmees': 'Ventes confirmées', 'signe': 'Signé',
            'facture': 'Facturé', 'encaisse': 'Encaissé',
            'chantiers_retard': 'Chantiers en retard', 'dossiers_bloques': 'Dossiers bloqués',
        }
        suffix = ('à ce jour' if card == 'chantiers_retard'
                  or (card == 'dossiers_bloques' and f['blocked_cutoff'] is None)
                  else f['period_label'])
        return {
            'type': 'ir.actions.act_window',
            'name': '%s – %s' % (titles[card], suffix),
            'res_model': records._name,
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('id', 'in', records.ids)],
            'context': {'create': False},
            'target': 'current',
        }

    @api.model
    def export_excel(self, month=None, year=None, period_type='month',
                     quarter=None, company_id=None, date_from=None, date_to=None,
                     payment_term_id=None):
        """Excel file (base64): the Direction figures and a Calculs sheet."""
        import xlsxwriter

        data = self.get_dashboard_data(
            month=month, year=year, period_type=period_type, quarter=quarter,
            company_id=company_id, date_from=date_from, date_to=date_to,
            payment_term_id=payment_term_id)
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
        for label, key in (('Signé', 'signe'), ('Facturé', 'facture'), ('Encaissé', 'encaisse')):
            row += 1
            sheet.write(row, 0, label, label_fmt)
            sheet.write_number(row, 1, cash[key], money_fmt)

        calc = workbook.add_worksheet('Calculs')
        calc.set_column(0, 0, 26)
        calc.set_column(1, 1, 90)
        calc.write_row(0, 0, ['Champ', 'Formule / description'], header_fmt)
        for i, (label, key) in enumerate((
                ('CA NET', 'ca_net'), ('VENTES CONFIRMÉES', 'ventes_confirmees'),
                ('TX CONVERSION', 'tx_conversion'), ('CHANTIERS EN RETARD', 'chantiers_retard'),
                ('DOSSIERS BLOQUÉS', 'dossiers_bloques'), ('SIGNÉ', 'signe'),
                ('FACTURÉ', 'facture'), ('ENCAISSÉ', 'encaisse')), start=1):
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
