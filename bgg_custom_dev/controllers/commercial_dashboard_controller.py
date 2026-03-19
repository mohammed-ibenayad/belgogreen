# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class CommercialDashboardController(http.Controller):

    @http.route('/commercial/dashboard/data', type='jsonrpc', auth='user')
    def get_dashboard_data(self, month=None, year=None):
        """API endpoint to get commercial dashboard data."""
        dashboard = request.env['commercial.dashboard']
        return dashboard.get_dashboard_data(month=month, year=year)
