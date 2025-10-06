# -*- coding: utf-8 -*-
# from odoo import http


# class AiOdooSuggest(http.Controller):
#     @http.route('/ai_odoo_suggest/ai_odoo_suggest', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ai_odoo_suggest/ai_odoo_suggest/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ai_odoo_suggest.listing', {
#             'root': '/ai_odoo_suggest/ai_odoo_suggest',
#             'objects': http.request.env['ai_odoo_suggest.ai_odoo_suggest'].search([]),
#         })

#     @http.route('/ai_odoo_suggest/ai_odoo_suggest/objects/<model("ai_odoo_suggest.ai_odoo_suggest"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ai_odoo_suggest.object', {
#             'object': obj
#         })

