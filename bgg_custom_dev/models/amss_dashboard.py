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
        "(le suivi des annulations se fait via TX ANNULATION)."),
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
    def _period_orders(self, date_start, date_end, company_ids, states):
        return self.env['sale.order'].sudo().search([
            ('date_order', '>=', fields.Datetime.to_string(date_start)),
            ('date_order', '<', fields.Datetime.to_string(date_end)),
            ('state', 'in', states),
            ('company_id', 'in', company_ids),
        ])

    @api.model
    def _sales_figures(self, date_start, date_end, company_ids):
        """CA NET, Ventes Confirmées and TX CONVERSION of a period, computed
        exactly as in Suivi Commercial (same helpers) but for every order and
        appointment of the companies."""
        commercial = self.env['commercial.dashboard']
        orders = self._period_orders(date_start, date_end, company_ids, ['sale', 'done', 'cancel'])
        fin = commercial._compute_financial_kpis(orders)

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
        ventes_signees = fin['nbre_vies'] + fin['ventes_annulees']
        return {
            'ca_net': round(fin['ca_brut'] - fin['ca_annule'], 2),
            'ventes_confirmees': fin['nbre_vies'],
            'tx_conversion': round(ventes_signees / present * 100) if present else 0,
        }

    @api.model
    def _admin_projects(self, company_ids):
        """Admin projects (linked to a sale order, templates excluded) of
        confirmed orders."""
        projects = self.env['project.project'].sudo().search([
            '|',
            ('sale_line_id', '!=', False),
            ('reinvoiced_sale_order_id', '!=', False),
            ('is_template', '=', False),
            ('company_id', 'in', company_ids),
        ])
        return projects.filtered(lambda p: p._get_dossier_order().state == 'sale')

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
    def _blocked_count(self, projects, cutoff=None):
        """Number of projects whose status is Bloqué: current status, or the
        status of the last update dated before `cutoff` (exclusive)."""
        if cutoff is None:
            return len(projects.filtered(lambda p: p.last_update_status == BLOCKED_STATUS))
        updates = self.env['project.update'].sudo().search([
            ('project_id', 'in', projects.ids),
            ('date', '<', cutoff),
        ], order='date desc, id desc')
        last_status = {}
        for update in updates:
            last_status.setdefault(update.project_id.id, update.status)
        return sum(1 for status in last_status.values() if status == BLOCKED_STATUS)

    @api.model
    def _cash_flow(self, date_start, date_end, company_ids):
        """Signé / Facturé / Encaissé (HT) of the orders confirmed in the
        period. Credit notes are deducted (signed amounts); the paid part of a
        document is (total − residual) / total of its HT amount, so a credit
        note reconciled with an invoice cancels out instead of counting as
        cash."""
        orders = self._period_orders(date_start, date_end, company_ids, ['sale', 'done'])
        moves = orders.invoice_ids.filtered(
            lambda m: m.state == 'posted' and m.move_type in ('out_invoice', 'out_refund'))
        facture = sum(moves.mapped('amount_untaxed_signed'))
        encaisse = sum(
            move.amount_untaxed_signed * (move.amount_total - move.amount_residual) / move.amount_total
            for move in moves if move.amount_total)
        return {
            'signe': round(sum(orders.mapped('amount_untaxed')), 2),
            'facture': round(facture, 2),
            'encaisse': round(encaisse, 2),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @api.model
    def get_filter_options(self):
        self._check_dashboard_access()
        companies = self.env.user.company_ids.sorted('name')
        return {'companies': [{'id': c.id, 'name': c.name} for c in companies]}

    @api.model
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, company_id=None, date_from=None, date_to=None):
        self._check_dashboard_access()
        date_start, date_end, period_label, month, year, quarter = \
            self.env['call.center.dashboard']._resolve_period(
                month, year, period_type, quarter, date_from, date_to)
        prev_start, prev_end = self._previous_range(date_start, date_end, period_type)
        company_ids = self._allowed_company_ids(company_id)
        today = fields.Date.context_today(self.with_context(tz=BGG_TZ))

        current = self._sales_figures(date_start, date_end, company_ids)
        previous = self._sales_figures(prev_start, prev_end, company_ids)

        projects = self._admin_projects(company_ids)
        blocked_now = self._blocked_count(projects, None if date_end > today else date_end)
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
            'cash_flow': self._cash_flow(date_start, date_end, company_ids),
        }

    @api.model
    def export_excel(self, month=None, year=None, period_type='month',
                     quarter=None, company_id=None, date_from=None, date_to=None):
        """Excel file (base64): the Direction figures and a Calculs sheet."""
        import xlsxwriter

        data = self.get_dashboard_data(
            month=month, year=year, period_type=period_type, quarter=quarter,
            company_id=company_id, date_from=date_from, date_to=date_to)
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
            ('TX CONVERSION', cards['tx_conversion'], pct_fmt, 'points'),
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
            "compte (pas seulement le groupe Commercial)."), wrap_fmt)

        workbook.close()
        return base64.b64encode(output.getvalue()).decode('utf-8')
