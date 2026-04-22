# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

QUARTER_NAMES_FR = {1: '1er', 2: '2ème', 3: '3ème', 4: '4ème'}

# Call centers carrying this display name are treated as "generic" — they
# belong to the Call Center group but must not be credited with revenue.
GENERIC_CALL_CENTER_NAMES = ['Call Center Générique']


class CallCenterDashboard(models.TransientModel):
    _name = 'call.center.dashboard'
    _description = 'Tableau de bord Call Center'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _call_center_partner_domain(self):
        """Domain selecting call-center partners eligible for the dashboard.

        Rule: `x_call_center_sale_owner_id` on sale.order is set to a res.partner,
        and that partner is linked to a res.users who belongs to the "Call Center"
        res.groups. We express this via partner.user_ids.group_ids.name.
        Generic call centers are excluded by name.
        """
        return [
            ('user_ids.group_ids.name', '=', 'Call Center'),
            ('name', 'not in', GENERIC_CALL_CENTER_NAMES),
        ]

    def _resolve_period(self, month, year, period_type, quarter, date_from, date_to):
        """Return (date_start, date_end, period_label, month, year, quarter).

        date_end is exclusive. Mirrors the period handling used by
        commercial.dashboard so the filter UX is identical.
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
        """Return eligible call centers (res.partner) to populate the filter dropdown."""
        partners = self.env['res.partner'].search(
            self._call_center_partner_domain(),
            order='name',
        )
        return {
            'call_centers': [{'id': p.id, 'name': p.name} for p in partners],
        }

    @api.model
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, date_from=None, date_to=None,
                           call_center_id=None):
        """Aggregate confirmed and cancelled sale-order amounts per call center."""
        date_start, date_end, period_label, month, year, quarter = self._resolve_period(
            month, year, period_type, quarter, date_from, date_to,
        )

        # Eligible call centers (columns)
        cc_domain = self._call_center_partner_domain()
        if call_center_id:
            cc_domain = cc_domain + [('id', '=', call_center_id)]
        call_centers = self.env['res.partner'].search(cc_domain, order='name')

        # Sale orders in period, attributed to one of our eligible call centers
        so_domain = [
            ('date_order', '>=', fields.Datetime.to_string(date_start)),
            ('date_order', '<', fields.Datetime.to_string(date_end)),
            ('state', 'in', ['sale', 'done', 'cancel']),
            ('x_call_center_sale_owner_id', 'in', call_centers.ids),
        ]
        sale_orders = self.env['sale.order'].search(so_domain)

        revenue_by_cc = {cc.id: 0.0 for cc in call_centers}
        cancelled_by_cc = {cc.id: 0.0 for cc in call_centers}
        count_revenue_by_cc = {cc.id: 0 for cc in call_centers}
        count_cancelled_by_cc = {cc.id: 0 for cc in call_centers}

        for so in sale_orders:
            cc_id = so.x_call_center_sale_owner_id.id
            if cc_id not in revenue_by_cc:
                continue  # safety net
            if so.state == 'cancel':
                cancelled_by_cc[cc_id] += so.amount_total
                count_cancelled_by_cc[cc_id] += 1
            else:
                revenue_by_cc[cc_id] += so.amount_total
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
        """Return the plain order list for the Details tab.

        Columns: reference, client, company, amount_total, invoice_status, date_order.
        """
        date_start, date_end, _pl, _m, _y, _q = self._resolve_period(
            month, year, period_type, quarter, date_from, date_to,
        )

        # Eligible call centers (generic excluded) for the base domain
        eligible_ids = self.env['res.partner'].search(self._call_center_partner_domain()).ids
        cc_filter = [call_center_id] if call_center_id else eligible_ids

        so_domain = [
            ('date_order', '>=', fields.Datetime.to_string(date_start)),
            ('date_order', '<', fields.Datetime.to_string(date_end)),
            ('state', 'in', ['sale', 'done', 'cancel']),
            ('x_call_center_sale_owner_id', 'in', cc_filter),
        ]
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
                'amount_total': round(so.amount_total, 2),
                'invoice_status': so.invoice_status,
                'invoice_status_label': invoice_labels.get(so.invoice_status, so.invoice_status or ''),
                'state': so.state,
                'state_label': state_labels.get(so.state, so.state or ''),
                'date_order': fields.Datetime.to_string(so.date_order) if so.date_order else '',
                'call_center_id': so.x_call_center_sale_owner_id.id,
                'call_center_name': so.x_call_center_sale_owner_id.name or '',
            })
        return {'orders': data}
