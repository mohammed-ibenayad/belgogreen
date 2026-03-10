# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    pv_report_logo = fields.Binary(
        string='PV Report Logo',
        help='Logo image for PV reports (recommended: 200x80px PNG with transparent background)'
    )
    pv_report_phone = fields.Char(
        string='PV Report Phone',
        help='Contact phone number for PV reports'
    )
    pv_report_email = fields.Char(
        string='PV Report Email',
        help='Contact email for PV reports'
    )
    pv_report_tagline = fields.Char(
        string='PV Report Tagline',
        help='Company tagline for PV reports (e.g., "Save your planet. Save your wallet.")'
    )
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
