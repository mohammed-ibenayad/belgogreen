# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json


class CommissionDashboardController(http.Controller):

    @http.route('/commission/dashboard/data', type='jsonrpc', auth='user')
    def get_dashboard_data(self):
        """API endpoint to get dashboard data"""
        dashboard = request.env['commission.dashboard']
        return dashboard.get_dashboard_data()

    @http.route('/commission/dashboard/refresh', type='jsonrpc', auth='user')
    def refresh_dashboard(self):
        """Refresh dashboard data only.

        Commission generation is handled exclusively by the sale order engine
        (button/bulk/cron), which enforces plan dates, company and duplicate
        checks. The dashboard must never create commissions.
        """
        dashboard = request.env['commission.dashboard']
        return dashboard.get_dashboard_data()
