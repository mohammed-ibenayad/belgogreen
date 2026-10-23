# -*- coding: utf-8 -*-

from odoo import api, fields, models


class DmsDirectory(models.Model):
    """A folder can belong to a company, like in Enterprise Documents.

    OCA dms takes the company of the storage only, so one storage holds
    folders of a single company. Here a folder takes its own company, else
    the one of its parent folder, else the one of the storage: the company
    switcher then shows only the folders of the selected companies (plus the
    folders shared by all companies).
    """
    _inherit = 'dms.directory'

    x_company_id = fields.Many2one('res.company', string='Société du dossier',
                                   help="Empty: the company of the parent folder (or of the storage).")
    company_id = fields.Many2one(related=False, compute='_compute_company_id', store=True,
                                 recursive=True, readonly=True)

    @api.depends('x_company_id', 'parent_id.company_id', 'storage_id.company_id')
    def _compute_company_id(self):
        for directory in self:
            directory.company_id = (directory.x_company_id or directory.parent_id.company_id
                                    or directory.storage_id.company_id)


class DmsFile(models.Model):
    _inherit = 'dms.file'

    x_company_id = fields.Many2one('res.company', string='Société du fichier',
                                   help="Empty: the company of the folder.")
    company_id = fields.Many2one(related=False, compute='_compute_company_id', store=True, readonly=True)

    @api.depends('x_company_id', 'directory_id.company_id')
    def _compute_company_id(self):
        for file in self:
            file.company_id = file.x_company_id or file.directory_id.company_id
