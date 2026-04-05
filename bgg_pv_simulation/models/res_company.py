# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    pv_default_cover_photo = fields.Binary(
        string='Default Cover Photo',
        help='Default cover page photo used for new PV simulations'
    )
    pv_default_cover_photo_filename = fields.Char(
        string='Default Cover Photo Filename'
    )
    pv_default_system_image = fields.Binary(
        string='Default System Image',
        help='Default system image used for new PV simulations'
    )
    pv_default_system_image_filename = fields.Char(
        string='Default System Image Filename'
    )
