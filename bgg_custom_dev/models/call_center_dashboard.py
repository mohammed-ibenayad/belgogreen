# -*- coding: utf-8 -*-

import io
import logging

from odoo import api, fields, models
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

QUARTER_NAMES_FR = {1: '1er', 2: '2ème', 3: '3ème', 4: '4ème'}


class CallCenterDashboard(models.TransientModel):
    _name = 'call.center.dashboard'
    _description = 'Tableau de bord Call Center'

    # ------------------------------------------------------------------
    # Period handling (mirrors commercial.dashboard so the UX is identical)
    # ------------------------------------------------------------------

    def _resolve_period(self, month, year, period_type, quarter, date_from, date_to):
        """Return (date_start, date_end, period_label, month, year, quarter).

        date_end is exclusive.
        """
        today = fields.Date.today()
        if not year:
            year = today.year
        if not month:
            month = today.month

        if period_type == 'custom' and date_from and date_to:
            df = fields.Date.to_date(date_from)
            dt = fields.Date.to_date(date_to)
            if dt < df:
                df, dt = dt, df
            date_start = df
            date_end = dt + relativedelta(days=1)
            period_label = f"DU {df.strftime('%d/%m/%Y')} AU {dt.strftime('%d/%m/%Y')}"
            month = df.month
            year = df.year
            quarter = (df.month - 1) // 3 + 1
        elif period_type == 'quarter':
            if not quarter:
                quarter = (month - 1) // 3 + 1
            q_start_month = (quarter - 1) * 3 + 1
            date_start = fields.Date.to_date(f'{year}-{q_start_month:02d}-01')
            date_end = date_start + relativedelta(months=3)
            period_label = f'{QUARTER_NAMES_FR.get(quarter, quarter)} TRIMESTRE {year}'
            month = q_start_month
        elif period_type == 'year':
            date_start = fields.Date.to_date(f'{year}-01-01')
            date_end = fields.Date.to_date(f'{year + 1}-01-01')
            period_label = str(year)
            quarter = None
        else:
            date_start = fields.Date.to_date(f'{year}-{month:02d}-01')
            date_end = date_start + relativedelta(months=1)
            quarter = (month - 1) // 3 + 1
            import locale
            try:
                locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
            except Exception:
                pass
            period_label = date_start.strftime('%B %Y').upper()

        return date_start, date_end, period_label, month, year, quarter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @api.model
    def get_filter_options(self):
        """Distinct call-center partners that have ever been the owner of a
        sale order. Populates the filter dropdown.
        """
        partners = self.env['sale.order'].search(
            [('x_call_center_sale_owner_id', '!=', False)],
        ).mapped('x_call_center_sale_owner_id').sorted('name')
        return {
            'call_centers': [{'id': p.id, 'name': p.name} for p in partners],
        }

    @api.model
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, date_from=None, date_to=None,
                           call_center_id=None):
        """Aggregate confirmed and cancelled sale-order amounts (HT) per call
        center for the given period.
        """
        date_start, date_end, period_label, month, year, quarter = self._resolve_period(
            month, year, period_type, quarter, date_from, date_to,
        )

        so_domain = [
            ('date_order', '>=', fields.Datetime.to_string(date_start)),
            ('date_order', '<', fields.Datetime.to_string(date_end)),
            ('state', 'in', ['sale', 'done', 'cancel']),
            ('x_call_center_sale_owner_id', '!=', False),
        ]
        if call_center_id:
            so_domain.append(('x_call_center_sale_owner_id', '=', call_center_id))

        sale_orders = self.env['sale.order'].search(so_domain)

        # Columns: call centers actually appearing in the period's data.
        call_centers = sale_orders.mapped('x_call_center_sale_owner_id').sorted('name')

        revenue_by_cc = {cc.id: 0.0 for cc in call_centers}
        cancelled_by_cc = {cc.id: 0.0 for cc in call_centers}
        count_revenue_by_cc = {cc.id: 0 for cc in call_centers}
        count_cancelled_by_cc = {cc.id: 0 for cc in call_centers}

        for so in sale_orders:
            cc_id = so.x_call_center_sale_owner_id.id
            if cc_id not in revenue_by_cc:
                continue
            if so.state == 'cancel':
                cancelled_by_cc[cc_id] += so.amount_untaxed
                count_cancelled_by_cc[cc_id] += 1
            else:
                revenue_by_cc[cc_id] += so.amount_untaxed
                count_revenue_by_cc[cc_id] += 1

        company = self.env.user.company_id
        currency_info = {
            'symbol': company.currency_id.symbol,
            'position': company.currency_id.position,
            'decimal_places': company.currency_id.decimal_places,
        }

        return {
            'call_centers': [{'id': cc.id, 'name': cc.name} for cc in call_centers],
            'revenue': {str(k): round(v, 2) for k, v in revenue_by_cc.items()},
            'cancelled': {str(k): round(v, 2) for k, v in cancelled_by_cc.items()},
            'revenue_count': {str(k): v for k, v in count_revenue_by_cc.items()},
            'cancelled_count': {str(k): v for k, v in count_cancelled_by_cc.items()},
            'revenue_total': round(sum(revenue_by_cc.values()), 2),
            'cancelled_total': round(sum(cancelled_by_cc.values()), 2),
            'revenue_count_total': sum(count_revenue_by_cc.values()),
            'cancelled_count_total': sum(count_cancelled_by_cc.values()),
            'period_label': period_label,
            'current_month': month,
            'current_year': year,
            'current_quarter': quarter,
            'currency': currency_info,
        }

    @api.model
    def get_orders_list(self, month=None, year=None, period_type='month',
                        quarter=None, date_from=None, date_to=None,
                        call_center_id=None):
        """Return the plain order list for the Details tab (HT amount)."""
        date_start, date_end, _pl, _m, _y, _q = self._resolve_period(
            month, year, period_type, quarter, date_from, date_to,
        )

        so_domain = [
            ('date_order', '>=', fields.Datetime.to_string(date_start)),
            ('date_order', '<', fields.Datetime.to_string(date_end)),
            ('state', 'in', ['sale', 'done', 'cancel']),
            ('x_call_center_sale_owner_id', '!=', False),
        ]
        if call_center_id:
            so_domain.append(('x_call_center_sale_owner_id', '=', call_center_id))

        orders = self.env['sale.order'].search(so_domain, order='date_order desc, name desc')

        state_labels = dict(self.env['sale.order']._fields['state']._description_selection(self.env))
        invoice_labels = dict(self.env['sale.order']._fields['invoice_status']._description_selection(self.env))

        data = []
        for so in orders:
            data.append({
                'id': so.id,
                'name': so.name,
                'partner_name': so.partner_id.display_name or '',
                'company_name': so.company_id.name or '',
                'amount_untaxed': round(so.amount_untaxed, 2),
                'invoice_status': so.invoice_status,
                'invoice_status_label': invoice_labels.get(so.invoice_status, so.invoice_status or ''),
                'state': so.state,
                'state_label': state_labels.get(so.state, so.state or ''),
                'date_order': fields.Datetime.to_string(so.date_order) if so.date_order else '',
                'call_center_id': so.x_call_center_sale_owner_id.id,
                'call_center_name': so.x_call_center_sale_owner_id.name or '',
            })
        return {'orders': data}

    # ------------------------------------------------------------------
    # Excel export (3 sheets: Synthèse, Commandes, Calculs)
    # ------------------------------------------------------------------

    @api.model
    def export_excel(self, month=None, year=None, period_type='month',
                     quarter=None, date_from=None, date_to=None,
                     call_center_id=None):
        import xlsxwriter

        summary = self.get_dashboard_data(
            month=month, year=year, period_type=period_type, quarter=quarter,
            date_from=date_from, date_to=date_to, call_center_id=call_center_id,
        )
        details = self.get_orders_list(
            month=month, year=year, period_type=period_type, quarter=quarter,
            date_from=date_from, date_to=date_to, call_center_id=call_center_id,
        )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Formats reused across sheets (same palette as Suivi Commercial)
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#2c3e50', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Arial', 'font_size': 11,
        })
        total_header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#017e84', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Arial', 'font_size': 11,
        })
        blue_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#17a2b8', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Arial', 'font_size': 10,
        })
        green_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#28a745', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Arial', 'font_size': 10,
        })
        red_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#dc3545', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Arial', 'font_size': 10,
        })
        label_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#f8f9fa', 'border': 1,
            'font_name': 'Arial', 'font_size': 10,
        })
        cell_fmt = workbook.add_format({
            'border': 1, 'align': 'center',
            'font_name': 'Arial', 'font_size': 10,
        })
        total_cell_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center',
            'bg_color': '#e8f5f5', 'font_color': '#017e84',
            'font_name': 'Arial', 'font_size': 10,
        })
        currency_fmt = workbook.add_format({
            'border': 1, 'align': 'right', 'num_format': '#,##0.00 €',
            'font_name': 'Arial', 'font_size': 10,
        })
        currency_total_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'right',
            'bg_color': '#e8f5f5', 'font_color': '#017e84',
            'num_format': '#,##0.00 €',
            'font_name': 'Arial', 'font_size': 10,
        })
        wrap_fmt = workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'top', 'text_wrap': True,
            'font_name': 'Arial', 'font_size': 10,
        })
        wrap_label_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#f8f9fa', 'border': 1,
            'align': 'left', 'valign': 'top', 'text_wrap': True,
            'font_name': 'Arial', 'font_size': 10,
        })

        # === Sheet 1: Synthèse ===
        synth = workbook.add_worksheet('Synthèse')
        ccs = summary['call_centers']
        n_cc = len(ccs)

        synth.set_column(0, 0, 22)
        synth.set_column(1, 1, 14)
        for i in range(n_cc + 1):
            synth.set_column(2 + i, 2 + i, 20)

        row = 0
        synth.merge_range(row, 0, row, 1, summary['period_label'], header_fmt)
        for i, cc in enumerate(ccs):
            synth.write(row, 2 + i, cc['name'], header_fmt)
        synth.write(row, 2 + n_cc, 'TOTAL', total_header_fmt)

        def get_cc(d, cc_id):
            return d.get(str(cc_id), 0)

        row = 1
        # Ventes confirmées (count)
        synth.write(row, 0, 'VENTES CONFIRMÉES', blue_fmt)
        synth.write(row, 1, 'Nombre', label_fmt)
        for i, cc in enumerate(ccs):
            synth.write_number(row, 2 + i, get_cc(summary['revenue_count'], cc['id']), cell_fmt)
        synth.write_number(row, 2 + n_cc, summary['revenue_count_total'], total_cell_fmt)
        row += 1

        # Revenu HT
        synth.write(row, 0, 'REVENU (HT)', green_fmt)
        synth.write(row, 1, 'Montant', label_fmt)
        for i, cc in enumerate(ccs):
            synth.write_number(row, 2 + i, get_cc(summary['revenue'], cc['id']), currency_fmt)
        synth.write_number(row, 2 + n_cc, summary['revenue_total'], currency_total_fmt)
        row += 1

        # Ventes annulées (count)
        synth.write(row, 0, 'VENTES ANNULÉES', red_fmt)
        synth.write(row, 1, 'Nombre', label_fmt)
        for i, cc in enumerate(ccs):
            synth.write_number(row, 2 + i, get_cc(summary['cancelled_count'], cc['id']), cell_fmt)
        synth.write_number(row, 2 + n_cc, summary['cancelled_count_total'], total_cell_fmt)
        row += 1

        # Montant annulé
        synth.write(row, 0, 'MONTANT ANNULÉ (HT)', red_fmt)
        synth.write(row, 1, 'Montant', label_fmt)
        for i, cc in enumerate(ccs):
            synth.write_number(row, 2 + i, get_cc(summary['cancelled'], cc['id']), currency_fmt)
        synth.write_number(row, 2 + n_cc, summary['cancelled_total'], currency_total_fmt)

        # === Sheet 2: Commandes ===
        orders_sheet = workbook.add_worksheet('Commandes')
        cols = [
            ('Référence', 14),
            ('Client', 28),
            ('Société', 22),
            ('Call Center', 22),
            ('Total HT', 14),
            ('Statut facturation', 18),
            ('Statut', 14),
            ('Date de commande', 20),
        ]
        for idx, (name, width) in enumerate(cols):
            orders_sheet.set_column(idx, idx, width)
            orders_sheet.write(0, idx, name, header_fmt)

        for r, o in enumerate(details['orders'], start=1):
            orders_sheet.write(r, 0, o['name'], cell_fmt)
            orders_sheet.write(r, 1, o['partner_name'], cell_fmt)
            orders_sheet.write(r, 2, o['company_name'], cell_fmt)
            orders_sheet.write(r, 3, o['call_center_name'], cell_fmt)
            orders_sheet.write_number(r, 4, o['amount_untaxed'], currency_fmt)
            orders_sheet.write(r, 5, o['invoice_status_label'], cell_fmt)
            orders_sheet.write(r, 6, o['state_label'], cell_fmt)
            orders_sheet.write(r, 7, o['date_order'], cell_fmt)

        # === Sheet 3: Calculs ===
        calc = workbook.add_worksheet('Calculs')
        calc.set_column(0, 0, 26)
        calc.set_column(1, 1, 58)
        calc.set_column(2, 2, 70)
        calc.write(0, 0, 'Champ', header_fmt)
        calc.write(0, 1, 'Formule', header_fmt)
        calc.write(0, 2, 'Description', header_fmt)

        calc_rows = [
            (blue_fmt, 'VENTES CONFIRMÉES',
             "Count(sale.order) où state ∈ {sale, done} et x_call_center_sale_owner_id renseigné",
             "Nombre de commandes confirmées (et non annulées) attribuées au call center sur la période."),
            (green_fmt, 'REVENU (HT)',
             'Σ amount_untaxed des commandes confirmées attribuées au call center',
             "Chiffre d'affaires HT généré par le call center sur la période (hors annulations)."),
            (red_fmt, 'VENTES ANNULÉES',
             "Count(sale.order) où state = cancel et x_call_center_sale_owner_id renseigné",
             "Nombre de commandes annulées attribuées au call center sur la période."),
            (red_fmt, 'MONTANT ANNULÉ (HT)',
             'Σ amount_untaxed des commandes annulées attribuées au call center',
             "Montant HT des commandes annulées attribuées au call center sur la période."),
        ]
        for r, (fmt, name, formula, description) in enumerate(calc_rows, start=1):
            calc.write(r, 0, name, fmt)
            calc.write(r, 1, formula, wrap_label_fmt)
            calc.write(r, 2, description, wrap_fmt)
            calc.set_row(r, 42)

        workbook.close()
        output.seek(0)

        import base64
        return base64.b64encode(output.read()).decode('utf-8')
