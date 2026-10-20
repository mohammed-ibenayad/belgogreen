# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Parent folder of the project folders: system parameter (folder name or id),
# else the top folder "Projects" (the Enterprise Documents workspace).
PARENT_PARAM = 'bgg_dms_project.parent_directory'
DEFAULT_PARENT_NAME = 'Projects'


class ProjectProject(models.Model):
    _inherit = 'project.project'

    x_dms_directory_id = fields.Many2one(
        'dms.directory',
        string='Dossier documents',
        copy=False,
        index='btree_not_null',
        ondelete='set null',
    )
    x_dms_file_count = fields.Integer(string='Documents', compute='_compute_dms_file_count')

    def _compute_dms_file_count(self):
        File = self.env['dms.file']
        for project in self:
            directory = project.x_dms_directory_id
            project.x_dms_file_count = File.search_count([('directory_id', 'child_of', directory.id)]) if directory else 0

    # ------------------------------------------------------------------
    # Folder of a new project
    # ------------------------------------------------------------------

    @api.model
    def _bgg_dms_parent_directory(self):
        Directory = self.env['dms.directory'].sudo()
        value = (self.env['ir.config_parameter'].sudo().get_param(PARENT_PARAM) or '').strip()
        if value.isdigit():
            return Directory.browse(int(value)).exists()
        return Directory.search([('name', '=', value or DEFAULT_PARENT_NAME), ('is_root_directory', '=', True)], limit=1)

    @api.model
    def _bgg_unique_child_name(self, parent, name):
        taken = set(parent.child_directory_ids.mapped('name'))
        name = (name or 'Projet').replace('/', '-').strip() or 'Projet'
        candidate, number = name, 2
        while candidate in taken:
            candidate = f"{name} ({number})"
            number += 1
        return candidate

    def _bgg_create_dms_directory(self):
        parent = self._bgg_dms_parent_directory()
        if not parent:
            _logger.warning("bgg_dms_project: no parent folder '%s' in DMS, no folder created for projects %s",
                            DEFAULT_PARENT_NAME, self.ids)
            return
        Directory = self.env['dms.directory'].sudo()
        for project in self:
            directory = Directory.create({
                'name': self._bgg_unique_child_name(parent, project.name),
                'parent_id': parent.id,
            })
            project.sudo().x_dms_directory_id = directory

    @api.model
    def _bgg_copy_subdirectories(self, source, target):
        """The sub-folders of a template folder (names only, no files)."""
        Directory = self.env['dms.directory'].sudo()
        for child in source.sudo().child_directory_ids:
            copy = Directory.create({'name': self._bgg_unique_child_name(target, child.name), 'parent_id': target.id})
            self._bgg_copy_subdirectories(child, copy)

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects.filtered(lambda p: not p.x_dms_directory_id)._bgg_create_dms_directory()
        return projects

    def copy(self, default=None):
        new_projects = super().copy(default)
        for source, new in zip(self, new_projects):
            if source.x_dms_directory_id and new.x_dms_directory_id:
                self._bgg_copy_subdirectories(source.x_dms_directory_id, new.x_dms_directory_id)
        return new_projects

    # ------------------------------------------------------------------
    # "Documents" button
    # ------------------------------------------------------------------

    def action_open_dms_files(self):
        self.ensure_one()
        if not self.x_dms_directory_id:
            self._bgg_create_dms_directory()
        directory = self.x_dms_directory_id
        if not directory:
            raise UserError(self.env._("Aucun dossier « %s » dans Documents (DMS) pour y créer le dossier du projet.",
                                       DEFAULT_PARENT_NAME))
        action = self.env['ir.actions.act_window']._for_xml_id('dms.action_dms_file')
        action.update({
            'name': directory.name,
            'domain': [('directory_id', 'child_of', directory.id)],
            'context': {'default_directory_id': directory.id, 'searchpanel_default_directory_id': directory.id},
        })
        return action

    # ------------------------------------------------------------------
    # Projects moved from Enterprise Documents (bgg_documents_dms)
    # ------------------------------------------------------------------

    @api.model
    def _bgg_link_converted_directories(self):
        """Link each project to the DMS folder made from its Documents
        folder (project.documents_folder_id, through the copy's map)."""
        cr = self.env.cr
        cr.execute("""SELECT to_regclass('bgg_documents_dms_map') IS NOT NULL,
                             EXISTS (SELECT 1 FROM information_schema.columns
                                     WHERE table_name = 'project_project' AND column_name = 'documents_folder_id')""")
        has_map, has_folder = cr.fetchone()
        if not (has_map and has_folder):
            return 0
        self.env.flush_all()
        cr.execute("""UPDATE project_project p SET x_dms_directory_id = m.directory_id
                        FROM bgg_documents_dms_map m
                       WHERE m.document_id = p.documents_folder_id AND m.directory_id IS NOT NULL
                         AND p.x_dms_directory_id IS NULL
                         AND EXISTS (SELECT 1 FROM dms_directory d WHERE d.id = m.directory_id)""")
        linked = cr.rowcount
        self.invalidate_model(['x_dms_directory_id'])
        _logger.info("bgg_dms_project: %s project(s) linked to their DMS folder", linked)
        return linked
