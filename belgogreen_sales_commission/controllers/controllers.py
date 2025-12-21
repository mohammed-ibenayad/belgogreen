# -*- coding: utf-8 -*-
# from odoo import http


# class BelgogreenSalesCommission(http.Controller):
#     @http.route('/belgogreen_sales_commission/belgogreen_sales_commission', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/belgogreen_sales_commission/belgogreen_sales_commission/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('belgogreen_sales_commission.listing', {
#             'root': '/belgogreen_sales_commission/belgogreen_sales_commission',
#             'objects': http.request.env['belgogreen_sales_commission.belgogreen_sales_commission'].search([]),
#         })

#     @http.route('/belgogreen_sales_commission/belgogreen_sales_commission/objects/<model("belgogreen_sales_commission.belgogreen_sales_commission"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('belgogreen_sales_commission.object', {
#             'object': obj
#         })

