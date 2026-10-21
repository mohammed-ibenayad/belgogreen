# -*- coding: utf-8 -*-

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestFileSearch(TransactionCase):
    """"S00466" finds the files of the S00466 folders, sub-folders included."""

    def test_search_matches_folder_path(self):
        env = self.env
        access = env['dms.access.group'].create({'name': 'Internes (recherche)',
                                                 'group_ids': [Command.set(env.ref('base.group_user').ids)]})
        storage = env['dms.storage'].create({'name': 'Recherche', 'save_type': 'database'})
        root = env['dms.directory'].create({'name': 'Projets (recherche)', 'is_root_directory': True,
                                            'storage_id': storage.id, 'group_ids': [Command.set(access.ids)]})
        project = env['dms.directory'].create({'name': 'S00466 - MARCELLE Claude', 'parent_id': root.id})
        admin = env['dms.directory'].create({'name': 'ADMIN', 'parent_id': project.id})
        sss = env['dms.directory'].create({'name': 'S00466 - SSS - MARCELLE Claude', 'parent_id': root.id})
        other = env['dms.directory'].create({'name': 'S00467 - AUTRE', 'parent_id': root.id})
        File = env['dms.file']
        for name, directory in (('Commande - S00466.pdf', admin), ('Marcelle Claude - DF - MB.pdf', admin),
                                ('Marcelle Claude - DT - MB.pdf', project), ('Rapport SSS.pdf', sss),
                                ('Autre.pdf', other)):
            File.create({'name': name, 'directory_id': directory.id, 'content': 'JVBERi0xLjQ='})

        for view_type in ('kanban', 'list'):
            self.assertIn('directory_id', File.get_view(view_type=view_type)['arch'])
        arch = File.get_view(view_type='search')['arch']
        self.assertIn('directory_id.complete_name', arch)
        domain = ['|', ('name', 'ilike', 'S00466'), ('directory_id.complete_name', 'ilike', 'S00466')]
        self.assertCountEqual(File.search(domain).mapped('name'), [
            'Commande - S00466.pdf', 'Marcelle Claude - DF - MB.pdf', 'Marcelle Claude - DT - MB.pdf', 'Rapport SSS.pdf'])
