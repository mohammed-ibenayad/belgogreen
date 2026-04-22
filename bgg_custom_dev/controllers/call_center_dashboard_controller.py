# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class CallCenterDashboardController(http.Controller):

    @http.route('/call_center/dashboard/filters', type='jsonrpc', auth='user')
    def get_filter_options(self):
        return request.env['call.center.dashboard'].get_filter_options()

    @http.route('/call_center/dashboard/data', type='jsonrpc', auth='user')
    def get_dashboard_data(self, month=None, year=None, period_type='month',
                           quarter=None, date_from=None, date_to=None,
                           call_center_id=None):
        return request.env['call.center.dashboard'].get_dashboard_data(
            month=month,
            year=year,
            period_type=period_type,
            quarter=quarter,
            date_from=date_from,
            date_to=date_to,
            call_center_id=call_center_id,
        )

    @http.route('/call_center/dashboard/orders', type='jsonrpc', auth='user')
    def get_orders_list(self, month=None, year=None, period_type='month',
                        quarter=None, date_from=None, date_to=None,
                        call_center_id=None):
        return request.env['call.center.dashboard'].get_orders_list(
            month=month,
            year=year,
            period_type=period_type,
            quarter=quarter,
            date_from=date_from,
            date_to=date_to,
            call_center_id=call_center_id,
        )
