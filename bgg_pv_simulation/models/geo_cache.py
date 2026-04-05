# -*- coding: utf-8 -*-

from odoo import models, fields


class GeoCache(models.Model):
    _name = 'geo.cache'
    _description = 'Geocoding Cache'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        ondelete='cascade',
        index=True,
    )
    latitude = fields.Char(string='Latitude')
    longitude = fields.Char(string='Longitude')
    address = fields.Char(
        string='Adresse géocodée',
        help='Address string that was geocoded (to detect address changes)',
    )
