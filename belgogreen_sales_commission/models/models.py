# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class belgogreen_sales_commission(models.Model):
#     _name = 'belgogreen_sales_commission.belgogreen_sales_commission'
#     _description = 'belgogreen_sales_commission.belgogreen_sales_commission'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

