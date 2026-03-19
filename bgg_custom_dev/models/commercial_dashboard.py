# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class CommercialDashboard(models.TransientModel):
    _name = 'commercial.dashboard'
    _description = 'Tableau de bord Commercial'

    @api.model
    def get_dashboard_data(self, month=None, year=None):
        """Get commercial dashboard data for the given month/year.

        Returns a dict with:
        - users: list of user data (name, id)
        - rdv_call: appointment stats for CNT types per user
        - rdv_commercial: appointment stats for COM types per user
        - financial: financial KPIs per user
        - month_label: display label for the selected month
        - current_month/current_year: selected period
        """
        today = fields.Date.today()
        if not month:
            month = today.month
        if not year:
            year = today.year

        # Date range for the selected month
        date_start = fields.Date.to_date(f'{year}-{month:02d}-01')
        date_end = date_start + relativedelta(months=1)

        # Get month label
        import locale
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        except Exception:
            pass
        month_label = date_start.strftime('%B %Y').upper()

        # Get appointment type IDs
        cnt_types = self.env['appointment.type'].search([
            ('x_appointment_ref', 'like', '%CNT')
        ])
        com_types = self.env['appointment.type'].search([
            ('x_appointment_ref', 'like', '%COM')
        ])

        cnt_type_ids = cnt_types.ids
        com_type_ids = com_types.ids

        # Get all calendar events for the period with relevant appointment types
        all_type_ids = cnt_type_ids + com_type_ids
        events = self.env['calendar.event'].search([
            ('start', '>=', fields.Datetime.to_string(date_start)),
            ('start', '<', fields.Datetime.to_string(date_end)),
            ('appointment_type_id', 'in', all_type_ids),
        ])

        # Collect unique users from events
        user_ids_set = set()
        for event in events:
            if event.user_id:
                user_ids_set.add(event.user_id.id)

        # Also get users from sale orders in the period
        sale_orders = self.env['sale.order'].search([
            ('date_order', '>=', fields.Datetime.to_string(date_start)),
            ('date_order', '<', fields.Datetime.to_string(date_end)),
            ('state', 'in', ['sale', 'done', 'cancel']),
        ])
        for so in sale_orders:
            if so.user_id:
                user_ids_set.add(so.user_id.id)

        # Get user records and sort by name
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

        # Build per-user financial data from sale orders
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

        # Get currency info
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
            'month_label': month_label,
            'current_month': month,
            'current_year': year,
            'currency': currency_info,
        }

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
