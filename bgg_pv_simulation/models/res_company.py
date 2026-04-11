# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    pv_default_cover_photo = fields.Binary(
        string='Photo de couverture par défaut',
        help='Photo de couverture par défaut utilisée pour les nouvelles simulations PV'
    )
    pv_default_cover_photo_filename = fields.Char(
        string='Nom du fichier photo de couverture par défaut'
    )
    pv_default_system_image = fields.Binary(
        string='Image système par défaut',
        help='Image système par défaut utilisée pour les nouvelles simulations PV'
    )
    pv_default_system_image_filename = fields.Char(
        string='Nom du fichier image système par défaut'
    )
