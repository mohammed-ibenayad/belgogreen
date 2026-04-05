# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    geo_latitude = fields.Char(
        string='Latitude (cache)',
        help='Cached latitude from Google Geocoding API',
    )
    geo_longitude = fields.Char(
        string='Longitude (cache)',
        help='Cached longitude from Google Geocoding API',
    )
