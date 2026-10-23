# -*- coding: utf-8 -*-

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestProjectDirectory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        access = env['dms.access.group'].create({
            'name': 'Internes (test projets)', 'perm_create': True, 'perm_write': True, 'perm_unlink': True,
            'group_ids': [Command.set(env.ref('base.group_user').ids)],
        })
        storage = env['dms.storage'].create({'name': 'Documents (test)', 'save_type': 'database'})
        cls.projects_dir = env['dms.directory'].search([('name', '=', 'Projects'), ('is_root_directory', '=', True)])
        if not cls.projects_dir:
            cls.projects_dir = env['dms.directory'].create({
                'name': 'Projects', 'is_root_directory': True, 'storage_id': storage.id,
                'group_ids': [Command.set(access.ids)],
            })

    def test_new_project_gets_its_folder(self):
        project = self.env['project.project'].create({'name': 'S09999 - DUPONT Marie'})
        self.assertEqual(project.x_dms_directory_id.parent_id, self.projects_dir)
        self.assertEqual(project.x_dms_directory_id.name, 'S09999 - DUPONT Marie')
        twin = self.env['project.project'].create({'name': 'S09999 - DUPONT Marie'})
        self.assertEqual(twin.x_dms_directory_id.name, 'S09999 - DUPONT Marie (2)')

    def test_project_folder_takes_the_project_company(self):
        company = self.env['res.company'].create({'name': 'NATUR (test projets)'})
        project = self.env['project.project'].create({'name': 'S09998 - MARTIN Paul', 'company_id': company.id})
        self.assertEqual(project.x_dms_directory_id.company_id, company)
        no_company = self.env['project.project'].create({'name': 'S09997 - Sans société', 'company_id': False})
        self.assertEqual(no_company.x_dms_directory_id.company_id, self.projects_dir.company_id)

    def test_template_subfolders_and_button(self):
        template = self.env['project.project'].create({'name': 'AMSS - Tâches Avant - Installation (test)'})
        admin = self.env['dms.directory'].create({'name': 'ADMIN', 'parent_id': template.x_dms_directory_id.id})
        self.env['dms.directory'].create({'name': 'Photos', 'parent_id': admin.id})
        project = template.copy({'name': 'S09998 - MARCELLE Claude'})
        self.assertEqual(project.x_dms_directory_id.name, 'S09998 - MARCELLE Claude')
        new_admin = project.x_dms_directory_id.child_directory_ids
        self.assertEqual(new_admin.mapped('name'), ['ADMIN'])
        self.assertEqual(new_admin.child_directory_ids.mapped('name'), ['Photos'])

        self.env['dms.file'].create({'name': 'Commande - S09998.pdf', 'directory_id': new_admin.id,
                                     'content': 'JVBERi0xLjQ='})
        self.assertEqual(project.x_dms_file_count, 1)
        action = project.action_open_dms_files()
        self.assertEqual(self.env['dms.file'].search(action['domain']).mapped('name'), ['Commande - S09998.pdf'])
        self.assertEqual(action['context']['default_directory_id'], project.x_dms_directory_id.id)

    def test_french_projects_folder(self):
        self.projects_dir.name = 'Projets'
        project = self.env['project.project'].create({'name': 'S09997 - Projet FR'})
        self.assertEqual(project.x_dms_directory_id.parent_id, self.projects_dir)

    def test_folder_holding_the_project_folders(self):
        old = self.env['project.project'].create({'name': 'Ancien projet'})
        self.projects_dir.name = 'Dossiers clients'
        project = self.env['project.project'].create({'name': 'Nouveau projet'})
        self.assertEqual(project.x_dms_directory_id.parent_id, old.x_dms_directory_id.parent_id)

    def test_no_projects_folder(self):
        self.env['project.project'].search([]).x_dms_directory_id = False
        self.projects_dir.name = 'Projets archivés'
        project = self.env['project.project'].create({'name': 'Sans dossier parent'})
        self.assertFalse(project.x_dms_directory_id)
        with self.assertRaises(UserError):
            project.action_open_dms_files()

    def test_link_converted_projects(self):
        cr = self.env.cr
        project = self.env['project.project'].create({'name': 'Projet Documents Enterprise'})
        old_directory = project.x_dms_directory_id
        project.x_dms_directory_id = False
        self.env.flush_all()
        # as with Enterprise documents_project and bgg_documents_dms
        cr.execute("ALTER TABLE project_project ADD COLUMN IF NOT EXISTS documents_folder_id INTEGER")
        cr.execute("CREATE TABLE IF NOT EXISTS bgg_documents_dms_map "
                   "(document_id INTEGER PRIMARY KEY, directory_id INTEGER, file_id INTEGER)")
        cr.execute("UPDATE project_project SET documents_folder_id = 999001 WHERE id = %s", [project.id])
        cr.execute("INSERT INTO bgg_documents_dms_map VALUES (999001, %s, NULL)", [old_directory.id])
        self.assertEqual(self.env['project.project']._bgg_link_converted_directories(), 1)
        self.assertEqual(project.x_dms_directory_id, old_directory)
