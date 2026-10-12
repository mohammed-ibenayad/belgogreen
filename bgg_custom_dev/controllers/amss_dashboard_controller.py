# -*- coding: utf-8 -*-

import base64

from odoo import http
from odoo.http import request


class AmssDashboardController(http.Controller):
    """AMSS Management dashboard. Access to the Direction group is checked by
    the model methods."""

    @http.route('/amss/dashboard/filters', type='jsonrpc', auth='user')
    def get_filter_options(self):
        return request.env['amss.management.dashboard'].get_filter_options()

    @http.route('/amss/dashboard/data', type='jsonrpc', auth='user')
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, company_id=None, date_from=None, date_to=None,
                           payment_term_id=None):
        return request.env['amss.management.dashboard'].get_dashboard_data(
            month=month, year=year, period_type=period_type, quarter=quarter,
            company_id=company_id, date_from=date_from, date_to=date_to,
            payment_term_id=payment_term_id,
        )

    @http.route('/amss/dashboard/open', type='jsonrpc', auth='user')
    def open_card(self, card, month=None, year=None, period_type='month', quarter=None,
                  company_id=None, date_from=None, date_to=None, payment_term_id=None):
        return request.env['amss.management.dashboard'].open_card(
            card, month=month, year=year, period_type=period_type, quarter=quarter,
            company_id=company_id, date_from=date_from, date_to=date_to,
            payment_term_id=payment_term_id,
        )

    @http.route('/amss/dashboard/export', type='http', auth='user')
    def export_excel(self, month=None, year=None, period_type='month',
                     quarter=None, company_id=None, date_from=None, date_to=None,
                     payment_term_id=None):
        b64_data = request.env['amss.management.dashboard'].export_excel(
            month=int(month) if month else None,
            year=int(year) if year else None,
            period_type=period_type,
            quarter=int(quarter) if quarter else None,
            company_id=int(company_id) if company_id else None,
            date_from=date_from, date_to=date_to,
            payment_term_id=int(payment_term_id) if payment_term_id else None,
        )
        if period_type == 'custom' and date_from and date_to:
            suffix = f"{date_from.replace('-', '')}_{date_to.replace('-', '')}"
        elif period_type == 'year':
            suffix = f"{year}"
        elif period_type == 'quarter':
            suffix = f"T{quarter}_{year}"
        else:
            suffix = f"{int(month):02d}_{year}" if month else "periode"
        filename = f"amss_management_direction_{suffix}.xlsx"
        return request.make_response(
            base64.b64decode(b64_data),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
            ],
        )
