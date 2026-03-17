# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    phone_2 = fields.Char(
        string='2nd Phone',
        help='Second phone number for the contact',
    )
