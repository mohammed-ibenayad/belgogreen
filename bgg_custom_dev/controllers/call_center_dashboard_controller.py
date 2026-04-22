# -*- coding: utf-8 -*-

import base64

from odoo import fields, http
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

    @http.route('/call_center/dashboard/export', type='http', auth='user')
    def export_excel(self, month=None, year=None, period_type='month',
                     quarter=None, date_from=None, date_to=None,
                     call_center_id=None):
        dashboard = request.env['call.center.dashboard']
        month = int(month) if month else None
        year = int(year) if year else None
        quarter = int(quarter) if quarter else None
        call_center_id = int(call_center_id) if call_center_id else None

        b64_data = dashboard.export_excel(
            month=month, year=year, period_type=period_type,
            quarter=quarter, date_from=date_from, date_to=date_to,
            call_center_id=call_center_id,
        )
        file_content = base64.b64decode(b64_data)

        today = fields.Date.today()
        eff_year = year or today.year
        eff_month = month or today.month
        if period_type == 'custom' and date_from and date_to:
            df = fields.Date.to_date(date_from)
            dt = fields.Date.to_date(date_to)
            if dt < df:
                df, dt = dt, df
            filename = (
                f"suivi_call_center_{df.strftime('%Y%m%d')}"
                f"_{dt.strftime('%Y%m%d')}.xlsx"
            )
        elif period_type == 'year':
            filename = f'suivi_call_center_{eff_year}.xlsx'
        elif period_type == 'quarter':
            eff_quarter = quarter or ((eff_month - 1) // 3 + 1)
            filename = f'suivi_call_center_T{eff_quarter}_{eff_year}.xlsx'
        else:
            filename = f'suivi_call_center_{eff_month:02d}_{eff_year}.xlsx'

        return request.make_response(
            file_content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
            ],
        )
