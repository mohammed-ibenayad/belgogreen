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
        """Refresh dashboard data and optionally generate commissions"""
        dashboard = request.env['commission.dashboard']

        # Generate commissions for the current user
        result = dashboard.generate_my_commissions()

        # Get updated dashboard data
        dashboard_data = dashboard.get_dashboard_data()

        # Add generation results to response
        dashboard_data['generation_result'] = result

        return dashboard_data
