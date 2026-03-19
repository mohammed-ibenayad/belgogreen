# -*- coding: utf-8 -*-

from odoo import http
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
