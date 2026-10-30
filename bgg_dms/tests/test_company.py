# -*- coding: utf-8 -*-

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestFolderCompany(TransactionCase):
    """A folder takes its own company, else the one of its parent folder: the
    company switcher shows only the folders of the selected companies."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.amss = env['res.company'].create({'name': 'AMSS (test)'})
        cls.natur = env['res.company'].create({'name': 'NATUR (test)'})
        access = env['dms.access.group'].create({'name': 'Internes (société)',
                                                 'group_ids': [Command.set(env.ref('base.group_user').ids)]})
        storage = env['dms.storage'].create({'name': 'Sociétés', 'save_type': 'database', 'company_id': False})
        Directory = env['dms.directory']
        cls.finance = Directory.create({'name': 'Finance (test)', 'is_root_directory': True,
                                        'storage_id': storage.id, 'group_ids': [Command.set(access.ids)]})
        cls.achats_amss = Directory.create({'name': 'Achats - AMSS', 'parent_id': cls.finance.id})
        cls.achats_natur = Directory.create({'name': 'Achats - NATUR', 'parent_id': cls.finance.id})
        cls.factures = Directory.create({'name': 'Factures', 'parent_id': cls.achats_amss.id})
        cls.file = env['dms.file'].create({'name': 'facture.pdf', 'directory_id': cls.factures.id,
                                           'content': 'JVBERi0xLjQ='})
        cls.user = env['res.users'].create({
            'name': 'Comptable AMSS', 'login': 'comptable_amss_dms',
            'company_id': cls.amss.id, 'company_ids': [Command.set((cls.amss | cls.natur).ids)],
            'group_ids': [Command.set((env.ref('base.group_user') | env.ref('dms.group_dms_user')).ids)]})

    def test_company_follows_the_folders(self):
        self.assertFalse(self.finance.company_id)
        self.achats_amss.x_company_id = self.amss
        self.achats_natur.x_company_id = self.natur
        self.assertEqual(self.factures.company_id, self.amss, "sub-folders follow")
        self.assertEqual(self.file.company_id, self.amss, "files follow")
        # moved under the other company's folder
        self.factures.parent_id = self.achats_natur
        self.assertEqual((self.factures.company_id, self.file.company_id), (self.natur, self.natur))
        # a file can have its own company
        self.file.x_company_id = self.amss
        self.assertEqual(self.file.company_id, self.amss)
        self.file.x_company_id = False
        self.assertEqual(self.file.company_id, self.natur)

    def test_switcher_filters_the_folders(self):
        self.achats_amss.x_company_id = self.amss
        self.achats_natur.x_company_id = self.natur
        Directory = self.env['dms.directory'].with_user(self.user)
        domain = [('id', 'child_of', self.finance.id)]
        only_amss = Directory.with_context(allowed_company_ids=self.amss.ids).search(domain)
        self.assertCountEqual(only_amss.mapped('name'), ['Finance (test)', 'Achats - AMSS', 'Factures'])
        both = Directory.with_context(allowed_company_ids=(self.amss | self.natur).ids).search(domain)
        self.assertEqual(len(both), 4)
        File = self.env['dms.file'].with_user(self.user)
        self.assertFalse(File.with_context(allowed_company_ids=self.natur.ids).search([('id', '=', self.file.id)]))
        self.assertTrue(File.with_context(allowed_company_ids=self.amss.ids).search([('id', '=', self.file.id)]))
