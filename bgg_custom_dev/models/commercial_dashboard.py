# -*- coding: utf-8 -*-

import io
import logging
from odoo import api, fields, models
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

QUARTER_NAMES_FR = {1: '1er', 2: '2ème', 3: '3ème', 4: '4ème'}


class CommercialDashboard(models.TransientModel):
    _name = 'commercial.dashboard'
    _description = 'Tableau de bord Commercial'

    @api.model
    def get_filter_options(self):
        """Return available users (Commercial group ID 59) and companies for filters."""
        commercial_group = self.env['res.groups'].browse(59)
        if commercial_group.exists():
            users = self.env['res.users'].browse(commercial_group.user_ids.ids).filtered(
                lambda u: u.active
            ).sorted('name')
        else:
            users = self.env['res.users'].search([
                ('share', '=', False),
                ('active', '=', True),
            ], order='name')
        companies = self.env['res.company'].sudo().search([], order='name')
        return {
            'users': [{'id': u.id, 'name': u.name} for u in users],
            'companies': [{'id': c.id, 'name': c.name} for c in companies],
        }

    @api.model
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, user_id=None, company_id=None):
        """Get commercial dashboard data for the given period.

        Args:
            month: month number (1-12)
            year: year number
            period_type: 'month', 'quarter', or 'year'
            quarter: quarter number (1-4), used when period_type='quarter'
            user_id: filter by specific user
            company_id: filter by specific company
        """
        today = fields.Date.today()
        if not year:
            year = today.year
        if not month:
            month = today.month

        # Compute date range based on period type
        if period_type == 'quarter':
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

        # Get appointment type IDs
        cnt_types = self.env['appointment.type'].search([
            ('x_appointment_ref', 'like', '%CNT')
        ])
        com_types = self.env['appointment.type'].search([
            ('x_appointment_ref', 'like', '%COM')
        ])

        cnt_type_ids = cnt_types.ids
        com_type_ids = com_types.ids
        all_type_ids = cnt_type_ids + com_type_ids

        # Build event domain
        event_domain = [
            ('start', '>=', fields.Datetime.to_string(date_start)),
            ('start', '<', fields.Datetime.to_string(date_end)),
            ('appointment_type_id', 'in', all_type_ids),
        ]
        if user_id:
            event_domain.append(('user_id', '=', user_id))
        if company_id:
            event_domain.append(('user_id.company_id', '=', company_id))

        events = self.env['calendar.event'].search(event_domain)

        # Get Commercial group user IDs to filter results
        commercial_group = self.env['res.groups'].browse(59)
        commercial_user_ids = set(commercial_group.user_ids.ids) if commercial_group.exists() else None

        # Collect unique users from events (only Commercial members)
        user_ids_set = set()
        for event in events:
            if event.user_id:
                if commercial_user_ids is None or event.user_id.id in commercial_user_ids:
                    user_ids_set.add(event.user_id.id)

        # Build sale order domain
        so_domain = [
            ('date_order', '>=', fields.Datetime.to_string(date_start)),
            ('date_order', '<', fields.Datetime.to_string(date_end)),
            ('state', 'in', ['sale', 'done', 'cancel']),
        ]
        if user_id:
            so_domain.append(('user_id', '=', user_id))
        if company_id:
            so_domain.append(('company_id', '=', company_id))

        sale_orders = self.env['sale.order'].search(so_domain)
        for so in sale_orders:
            if so.user_id:
                if commercial_user_ids is None or so.user_id.id in commercial_user_ids:
                    user_ids_set.add(so.user_id.id)

        # Get user records sorted by name
        users = self.env['res.users'].browse(list(user_ids_set)).sorted('name')

        # Build per-user appointment data
        rdv_call_data = {}
        rdv_commercial_data = {}

        for user in users:
            user_events_cnt = events.filtered(
                lambda e: e.user_id.id == user.id and e.appointment_type_id.id in cnt_type_ids
            )
            user_events_com = events.filtered(
                lambda e: e.user_id.id == user.id and e.appointment_type_id.id in com_type_ids
            )

            rdv_call_data[user.id] = self._count_appointment_statuses(user_events_cnt)
            rdv_commercial_data[user.id] = self._count_appointment_statuses(user_events_com)

        # Build per-user financial data
        financial_data = {}
        for user in users:
            user_orders = sale_orders.filtered(lambda o: o.user_id.id == user.id)
            financial_data[user.id] = self._compute_financial_kpis(user_orders)

        # Compute totals
        rdv_call_total = self._sum_appointment_data(rdv_call_data)
        rdv_commercial_total = self._sum_appointment_data(rdv_commercial_data)
        financial_total = self._sum_financial_data(financial_data)

        # Build user list
        user_list = [{'id': u.id, 'name': u.name} for u in users]

        # Compute derived KPIs per user
        derived_data = {}
        for user in users:
            uid = user.id
            call = rdv_call_data.get(uid, {})
            com = rdv_commercial_data.get(uid, {})
            fin = financial_data.get(uid, {})

            total_present_call = call.get('attended', 0)
            total_present_com = com.get('attended', 0)
            total_present = total_present_call + total_present_com
            total_call = call.get('total', 0)
            total_com = com.get('total', 0)

            nbre_vies = fin.get('nbre_vies', 0)
            ca_brut = fin.get('ca_brut', 0)
            ca_annule = fin.get('ca_annule', 0)
            ca_net = ca_brut - ca_annule

            tx_presence_call = (total_present_call / total_call * 100) if total_call else 0
            tx_presence_com = (total_present_com / total_com * 100) if total_com else 0
            tx_annulation = (ca_annule / ca_brut * 100) if ca_brut else 0
            panier_moyen = (ca_net / nbre_vies) if nbre_vies else 0
            tx_conversion = (nbre_vies / total_present * 100) if total_present else 0

            derived_data[uid] = {
                'tx_presence_call': round(tx_presence_call),
                'tx_presence_com': round(tx_presence_com),
                'nbre_vies': nbre_vies,
                'ca_brut': round(ca_brut, 2),
                'ca_net': round(ca_net, 2),
                'ca_annule': round(ca_annule, 2),
                'tx_annulation': round(tx_annulation),
                'panier_moyen': round(panier_moyen, 2),
                'tx_conversion': round(tx_conversion),
            }

        # Compute totals for derived KPIs
        total_present_call = rdv_call_total.get('attended', 0)
        total_present_com = rdv_commercial_total.get('attended', 0)
        total_present_all = total_present_call + total_present_com
        total_call_all = rdv_call_total.get('total', 0)
        total_com_all = rdv_commercial_total.get('total', 0)

        total_nbre_vies = financial_total.get('nbre_vies', 0)
        total_ca_brut = financial_total.get('ca_brut', 0)
        total_ca_annule = financial_total.get('ca_annule', 0)
        total_ca_net = total_ca_brut - total_ca_annule

        derived_total = {
            'tx_presence_call': round((total_present_call / total_call_all * 100) if total_call_all else 0),
            'tx_presence_com': round((total_present_com / total_com_all * 100) if total_com_all else 0),
            'nbre_vies': total_nbre_vies,
            'ca_brut': round(total_ca_brut, 2),
            'ca_net': round(total_ca_net, 2),
            'ca_annule': round(total_ca_annule, 2),
            'tx_annulation': round((total_ca_annule / total_ca_brut * 100) if total_ca_brut else 0),
            'panier_moyen': round((total_ca_net / total_nbre_vies) if total_nbre_vies else 0, 2),
            'tx_conversion': round((total_nbre_vies / total_present_all * 100) if total_present_all else 0),
        }

        # Currency info
        company = self.env.user.company_id
        currency_info = {
            'symbol': company.currency_id.symbol,
            'position': company.currency_id.position,
            'decimal_places': company.currency_id.decimal_places,
        }

        return {
            'users': user_list,
            'rdv_call': {str(k): v for k, v in rdv_call_data.items()},
            'rdv_call_total': rdv_call_total,
            'rdv_commercial': {str(k): v for k, v in rdv_commercial_data.items()},
            'rdv_commercial_total': rdv_commercial_total,
            'derived': {str(k): v for k, v in derived_data.items()},
            'derived_total': derived_total,
            'period_label': period_label,
            'current_month': month,
            'current_year': year,
            'current_quarter': quarter,
            'currency': currency_info,
        }

    @api.model
    def export_excel(self, month=None, year=None, period_type='month',
                     quarter=None, user_id=None, company_id=None):
        """Generate Excel file from dashboard data and return base64."""
        import xlsxwriter

        data = self.get_dashboard_data(
            month=month, year=year, period_type=period_type,
            quarter=quarter, user_id=user_id, company_id=company_id,
        )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Suivi Commercial')

        # Formats
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
        section_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#2c3e50', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Arial', 'font_size': 10,
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
            'border': 1, 'align': 'center', 'num_format': '#,##0.00 €',
            'font_name': 'Arial', 'font_size': 10,
        })
        currency_total_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center',
            'bg_color': '#e8f5f5', 'font_color': '#017e84',
            'num_format': '#,##0.00 €',
            'font_name': 'Arial', 'font_size': 10,
        })
        percent_fmt = workbook.add_format({
            'border': 1, 'align': 'center', 'num_format': '0%',
            'font_name': 'Arial', 'font_size': 10,
        })
        percent_total_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center',
            'bg_color': '#e8f5f5', 'font_color': '#017e84',
            'num_format': '0%',
            'font_name': 'Arial', 'font_size': 10,
        })

        users = data['users']
        n_users = len(users)

        # Column widths
        sheet.set_column(0, 0, 18)
        sheet.set_column(1, 1, 14)
        for i in range(n_users + 1):
            sheet.set_column(2 + i, 2 + i, 14)

        # Header row
        row = 0
        sheet.merge_range(row, 0, row, 1, data['period_label'], header_fmt)
        for i, user in enumerate(users):
            sheet.write(row, 2 + i, user['name'].split(' ')[0], header_fmt)
        sheet.write(row, 2 + n_users, 'TOTAL', total_header_fmt)

        def write_section(start_row, section_label, section_fmt_used, rows_data, is_currency=False, is_percent=False):
            """Write a group of rows. Returns next row index."""
            r = start_row
            for idx, (row_label, user_values, total_value) in enumerate(rows_data):
                if idx == 0 and len(rows_data) > 1:
                    sheet.merge_range(r, 0, r + len(rows_data) - 1, 0, section_label, section_fmt_used)
                elif len(rows_data) == 1:
                    sheet.write(r, 0, section_label, section_fmt_used)
                sheet.write(r, 1, row_label, label_fmt)
                for i, val in enumerate(user_values):
                    if is_currency:
                        sheet.write_number(r, 2 + i, val, currency_fmt)
                    elif is_percent:
                        sheet.write_number(r, 2 + i, val / 100.0 if val else 0, percent_fmt)
                    else:
                        sheet.write(r, 2 + i, val, cell_fmt)
                if is_currency:
                    sheet.write_number(r, 2 + n_users, total_value, currency_total_fmt)
                elif is_percent:
                    sheet.write_number(r, 2 + n_users, total_value / 100.0 if total_value else 0, percent_total_fmt)
                else:
                    sheet.write(r, 2 + n_users, total_value, total_cell_fmt)
                r += 1
            return r

        rdv_call = data['rdv_call']
        rdv_call_total = data['rdv_call_total']
        rdv_com = data['rdv_commercial']
        rdv_com_total = data['rdv_commercial_total']
        derived = data['derived']
        derived_total = data['derived_total']

        def get_user_vals(data_dict, key):
            return [data_dict.get(str(u['id']), {}).get(key, 0) for u in users]

        # RDV CALL CENTER
        row = 2
        call_rows = [
            ('Total', get_user_vals(rdv_call, 'total'), rdv_call_total.get('total', 0)),
            ('Présent', get_user_vals(rdv_call, 'attended'), rdv_call_total.get('attended', 0)),
            ('No-Show', get_user_vals(rdv_call, 'no_show'), rdv_call_total.get('no_show', 0)),
            ('Refusé', get_user_vals(rdv_call, 'cancelled'), rdv_call_total.get('cancelled', 0)),
            ('Réservé', get_user_vals(rdv_call, 'booked'), rdv_call_total.get('booked', 0)),
        ]
        row = write_section(row, 'RDV CALL CENTER', section_fmt, call_rows)

        # RDV COMMERCIAL
        row += 1
        com_rows = [
            ('Total', get_user_vals(rdv_com, 'total'), rdv_com_total.get('total', 0)),
            ('Présent', get_user_vals(rdv_com, 'attended'), rdv_com_total.get('attended', 0)),
            ('No-Show', get_user_vals(rdv_com, 'no_show'), rdv_com_total.get('no_show', 0)),
            ('Refusé', get_user_vals(rdv_com, 'cancelled'), rdv_com_total.get('cancelled', 0)),
            ('Réservé', get_user_vals(rdv_com, 'booked'), rdv_com_total.get('booked', 0)),
        ]
        row = write_section(row, 'RDV COMMERCIAL', section_fmt, com_rows)

        # TAUX PRÉSENCE
        row += 1
        presence_rows = [
            ('Call', get_user_vals(derived, 'tx_presence_call'), derived_total.get('tx_presence_call', 0)),
            ('Commercial', get_user_vals(derived, 'tx_presence_com'), derived_total.get('tx_presence_com', 0)),
        ]
        row = write_section(row, 'TAUX PRÉSENCE', blue_fmt, presence_rows, is_percent=True)

        # NBRE VENTES
        row += 1
        ventes_rows = [
            ('', get_user_vals(derived, 'nbre_vies'), derived_total.get('nbre_vies', 0)),
        ]
        row = write_section(row, 'NBRE VENTES', blue_fmt, ventes_rows)

        # CA BRUT
        row += 1
        row = write_section(row, 'CA BRUT', green_fmt, [
            ('', get_user_vals(derived, 'ca_brut'), derived_total.get('ca_brut', 0)),
        ], is_currency=True)

        # CA NET
        row = write_section(row, 'CA NET', green_fmt, [
            ('', get_user_vals(derived, 'ca_net'), derived_total.get('ca_net', 0)),
        ], is_currency=True)

        # ANNULÉ
        row = write_section(row, 'ANNULÉ', red_fmt, [
            ('', get_user_vals(derived, 'ca_annule'), derived_total.get('ca_annule', 0)),
        ], is_currency=True)

        # TX ANNULATION
        row = write_section(row, 'TX ANNULATION', section_fmt, [
            ('', get_user_vals(derived, 'tx_annulation'), derived_total.get('tx_annulation', 0)),
        ], is_percent=True)

        # PANIER MOYEN
        row = write_section(row, 'PANIER MOYEN', section_fmt, [
            ('', get_user_vals(derived, 'panier_moyen'), derived_total.get('panier_moyen', 0)),
        ], is_currency=True)

        # TX CONVERSION
        row = write_section(row, 'TX CONVERSION', section_fmt, [
            ('', get_user_vals(derived, 'tx_conversion'), derived_total.get('tx_conversion', 0)),
        ], is_percent=True)

        workbook.close()
        output.seek(0)

        import base64
        return base64.b64encode(output.read()).decode('utf-8')

    def _count_appointment_statuses(self, events):
        """Count appointments by status."""
        attended = len(events.filtered(lambda e: e.appointment_status == 'attended'))
        no_show = len(events.filtered(lambda e: e.appointment_status == 'no_show'))
        cancelled = len(events.filtered(lambda e: e.appointment_status == 'cancelled'))
        booked = len(events.filtered(lambda e: e.appointment_status == 'booked'))
        total = attended + no_show + cancelled + booked

        return {
            'total': total,
            'attended': attended,
            'no_show': no_show,
            'cancelled': cancelled,
            'booked': booked,
        }

    def _compute_financial_kpis(self, orders):
        """Compute financial KPIs from sale orders."""
        confirmed_orders = orders.filtered(lambda o: o.state in ('sale', 'done'))
        cancelled_orders = orders.filtered(lambda o: o.state == 'cancel')

        ca_brut = sum(confirmed_orders.mapped('amount_untaxed'))
        ca_annule = sum(cancelled_orders.mapped('amount_untaxed'))
        nbre_vies = len(confirmed_orders)

        return {
            'nbre_vies': nbre_vies,
            'ca_brut': ca_brut,
            'ca_annule': ca_annule,
        }

    def _sum_appointment_data(self, data_dict):
        """Sum appointment data across all users."""
        total = {'total': 0, 'attended': 0, 'no_show': 0, 'cancelled': 0, 'booked': 0}
        for user_data in data_dict.values():
            for key in total:
                total[key] += user_data.get(key, 0)
        return total

    def _sum_financial_data(self, data_dict):
        """Sum financial data across all users."""
        total = {'nbre_vies': 0, 'ca_brut': 0, 'ca_annule': 0}
        for user_data in data_dict.values():
            for key in total:
                total[key] += user_data.get(key, 0)
        return total
