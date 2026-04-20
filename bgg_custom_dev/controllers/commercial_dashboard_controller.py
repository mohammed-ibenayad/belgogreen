# -*- coding: utf-8 -*-

import base64
from odoo import fields, http
from odoo.http import request


class CommercialDashboardController(http.Controller):

    @http.route('/commercial/dashboard/data', type='jsonrpc', auth='user')
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, user_id=None, company_id=None):
        """API endpoint to get commercial dashboard data."""
        dashboard = request.env['commercial.dashboard']
        return dashboard.get_dashboard_data(
            month=month,
            year=year,
            period_type=period_type,
            quarter=quarter,
            user_id=user_id,
            company_id=company_id,
        )

    @http.route('/commercial/dashboard/filters', type='jsonrpc', auth='user')
    def get_filter_options(self):
        """API endpoint to get filter options (users, companies)."""
        dashboard = request.env['commercial.dashboard']
        return dashboard.get_filter_options()

    @http.route('/commercial/dashboard/export', type='http', auth='user')
    def export_excel(self, month=None, year=None, period_type='month',
                     quarter=None, user_id=None, company_id=None):
        """Download dashboard data as Excel file."""
        dashboard = request.env['commercial.dashboard']
        month = int(month) if month else None
        year = int(year) if year else None
        quarter = int(quarter) if quarter else None
        user_id = int(user_id) if user_id else None
        company_id = int(company_id) if company_id else None

        b64_data = dashboard.export_excel(
            month=month, year=year, period_type=period_type,
            quarter=quarter, user_id=user_id, company_id=company_id,
        )
        file_content = base64.b64decode(b64_data)

        # Build filename with the selected period (fallback to today for defaults)
        today = fields.Date.today()
        eff_year = year or today.year
        eff_month = month or today.month
        if period_type == 'year':
            filename = f'suivi_commercial_{eff_year}.xlsx'
        elif period_type == 'quarter':
            eff_quarter = quarter or ((eff_month - 1) // 3 + 1)
            filename = f'suivi_commercial_T{eff_quarter}_{eff_year}.xlsx'
        else:
            filename = f'suivi_commercial_{eff_month:02d}_{eff_year}.xlsx'

        return request.make_response(
            file_content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
            ],
        )
