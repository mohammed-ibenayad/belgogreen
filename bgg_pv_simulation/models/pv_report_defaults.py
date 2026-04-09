# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PvReportDefaults(models.Model):
    _name = 'pv.report.defaults'
    _description = 'PV Simulation Report Defaults'

    name = fields.Char(default='Report Defaults', required=True)

    default_cover_photo = fields.Binary(
        string='Photo de couverture par défaut',
        help='Photo utilisée par défaut sur la page de couverture du rapport PDF.',
    )
    default_cover_photo_filename = fields.Char(string='Cover Photo Filename')
    default_system_image = fields.Binary(
        string='Image système par défaut',
        help='Image utilisée par défaut pour les caractéristiques du système dans le rapport PDF.',
    )
    default_system_image_filename = fields.Char(string='System Image Filename')

    @api.model
    def get_defaults(self):
        """Return the singleton defaults record, creating it if needed."""
        record = self.search([], limit=1)
        if not record:
            record = self.create({'name': 'Report Defaults'})
        return record
