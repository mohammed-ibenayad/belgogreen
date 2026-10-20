# -*- coding: utf-8 -*-

import base64
import datetime

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.bgg_documents_dms.models.bgg_documents_dms import NO_FOLDER_NAME, STORAGE_NAME


@tagged('post_install', '-at_install')
class TestDocumentsToDms(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Doc = env['documents.document']
        groups = (env.ref('base.group_user') | env.ref('documents.group_documents_user')).ids
        cls.alice, cls.bob, cls.carl = (
            env['res.users'].create({'name': name, 'login': login, 'group_ids': [Command.set(groups)]})
            for name, login in (('Alice RH', 'alice_dms'), ('Bob RH', 'bob_dms'), ('Carl Admin', 'carl_dms')))
        cls.tag = env['documents.tag'].create({'name': 'Vendor Bills'})

        def folder(name, parent=None, access='edit', **vals):
            return cls.Doc.create(dict({'name': name, 'type': 'folder', 'access_internal': access,
                                        'folder_id': parent and parent.id}, **vals))

        def file(name, parent, data=b'%PDF-1.4 test', **vals):
            attachment = env['ir.attachment'].create({'name': name, 'raw': data, 'mimetype': vals.pop('mimetype', 'application/pdf')})
            return cls.Doc.create(dict({'name': name, 'type': 'binary', 'attachment_id': attachment.id,
                                        'folder_id': parent and parent.id, 'access_internal': 'edit'}, **vals))
        cls.folder, cls.file = staticmethod(folder), staticmethod(file)

        cls.projects = folder('Projects')
        cls.interne1 = folder('Interne', cls.projects)
        cls.interne2 = folder('Interne', cls.projects)
        cls.slashed = folder('S00258 - Patricia LICATA//CIALLELLA', cls.projects)
        cls.bill1 = file('facture.pdf', cls.interne1, tag_ids=[Command.set(cls.tag.ids)])
        cls.bill2 = file('facture.pdf', cls.interne1, data=b'%PDF-1.4 other')
        cls.old = file('ancien.pdf', cls.interne1, active=False)
        cls.photo = file('chantier.jpg', cls.slashed, mimetype='image/jpeg',
                         data=base64.b64decode('/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP////////////////////////////////////'
                                               '//////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBAB'
                                               'AAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA='))
        cls.sheet = file('Rapport rdv Marrakech', cls.projects, mimetype='application/o-spreadsheet', data=b'{}')
        cls.loose = file('sans dossier.pdf', None)
        cls.link = cls.Doc.create({'name': 'Lien', 'type': 'url', 'folder_id': cls.projects.id})
        # private top folder: only Alice (edit) and Bob (view)
        cls.hr = folder('Ali Lmoughit', access='none')
        cls.payslip = file('fiche de paie.pdf', folder('Fiche de paie', cls.hr, access='none'), access_internal='none')
        env['documents.access'].create([
            {'document_id': cls.payslip.id, 'partner_id': cls.alice.partner_id.id, 'role': 'edit'},
            {'document_id': cls.payslip.id, 'partner_id': cls.bob.partner_id.id, 'role': 'view'},
        ])
        # read-only top folder
        cls.procedures = folder('Procédures', access='view')

    def _dir(self, name, parent=None):
        domain = [('name', '=', name)]
        domain += [('parent_id', '=', parent.id)] if parent else [('is_root_directory', '=', True)]
        return self.env['dms.directory'].search(domain)

    def test_conversion(self):
        self.bill1.message_post(body='Facture validée')
        self.env.cr.execute("UPDATE documents_document SET create_date = %s WHERE id = %s",
                            [datetime.datetime(2025, 3, 4, 10, 0), self.bill1.id])
        counts = self.env['bgg.documents.dms']._convert()

        storage = self.env['dms.storage'].search([('name', '=', STORAGE_NAME)])
        self.assertEqual(storage.save_type, 'file')
        projects = self._dir('Projects')
        self.assertEqual(projects.storage_id, storage)
        self.assertCountEqual(projects.child_directory_ids.mapped('name'),
                              ['Interne', 'Interne (2)', 'S00258 - Patricia LICATA--CIALLELLA'])
        interne = self._dir('Interne', projects)
        files = self.env['dms.file'].with_context(active_test=False).search([('directory_id', '=', interne.id)])
        self.assertCountEqual(files.mapped('name'), ['facture.pdf', 'facture (2).pdf', 'ancien.pdf'])

        bill = files.filtered(lambda f: f.name == 'facture.pdf')
        self.assertEqual(base64.b64decode(bill.content), b'%PDF-1.4 test')
        self.assertEqual(bill.size, len(b'%PDF-1.4 test'))
        self.assertTrue(bill.human_size.startswith('13.00'), bill.human_size)
        self.assertEqual(bill.mimetype, 'application/pdf')
        self.assertEqual(bill.tag_ids.mapped('name'), ['Vendor Bills'])
        self.assertEqual(bill.create_date, datetime.datetime(2025, 3, 4, 10, 0))
        self.assertIn('Facture validée', bill.message_ids.mapped('body')[0])
        attachment = self.env['ir.attachment'].search([('res_model', '=', 'dms.file'), ('res_field', '=', 'content_file'), ('res_id', '=', bill.id)])
        self.assertEqual(attachment.store_fname, self.bill1.attachment_id.store_fname, "same stored file, not a copy")
        self.assertFalse(files.filtered(lambda f: f.name == 'ancien.pdf').active, "archived stays archived")

        photo = self.env['dms.file'].search([('name', '=', 'chantier.jpg')])
        self.assertTrue(photo.image_1920, "thumbnail of the image")
        self.assertEqual(self.env['dms.file'].search([('name', '=', 'sans dossier.pdf')]).directory_id.name, NO_FOLDER_NAME)
        self.assertFalse(self.env['dms.file'].search([('name', '=', 'Rapport rdv Marrakech')]), "spreadsheets dropped")
        self.assertEqual(counts['feuilles de calcul ignorées'], 1)
        self.assertEqual(counts['liens ignorés'], 1)

        # access per top folder
        self.assertEqual(projects.group_ids.group_ids, self.env.ref('base.group_user'))
        self.assertTrue(projects.group_ids.perm_write)
        hr = self._dir('Ali Lmoughit')
        self.assertFalse(hr.group_ids.group_ids)
        self.assertCountEqual(hr.group_ids.explicit_user_ids.ids, (self.alice | self.bob).ids)
        self.assertTrue(hr.group_ids.perm_write)
        procedures = self._dir('Procédures')
        self.assertEqual(procedures.group_ids.group_ids, self.env.ref('base.group_user'))
        self.assertFalse(procedures.group_ids.perm_write)
        File = self.env['dms.file']
        payslip = File.search([('name', '=', 'fiche de paie.pdf')])
        self.assertTrue(self.carl.has_group('dms.group_dms_user'), "Documents users get the dms right")
        self.assertTrue(File.with_user(self.alice).search([('id', '=', payslip.id)]))
        self.assertFalse(File.with_user(self.carl).search([('id', '=', payslip.id)]), "private folder")
        self.assertTrue(File.with_user(self.carl).search([('id', '=', bill.id)]), "open folder")

        # a new run adds only the new documents
        new = self.file('nouvelle facture.pdf', self.interne1)
        counts = self.env['bgg.documents.dms']._convert()
        self.assertEqual(counts.get('fichiers'), 1)
        self.assertEqual(counts.get('dossiers', 0), 0)
        self.assertTrue(self.env['dms.file'].search([('name', '=', 'nouvelle facture.pdf'), ('directory_id', '=', interne.id)]))
        self.assertTrue(new)

        # Documents removed: its attachments go, the dms content stays
        source_attachments = (self.bill1 | self.bill2 | self.photo).attachment_id
        source_attachments.unlink()
        bill.invalidate_recordset()
        self.assertEqual(base64.b64decode(bill.content), b'%PDF-1.4 test')

    def test_files_above_the_dms_size_limit(self):
        self.env['ir.config_parameter'].set_param('dms.binary_max_size', 1)
        self.file('video chantier.mp4', self.interne1, data=b'0' * (1024 * 1024 + 500 * 1024), mimetype='video/mp4')
        self.env['bgg.documents.dms']._convert()
        self.assertEqual(self.env['dms.file']._get_binary_max_size(), 2)
        self.assertTrue(self.env['dms.file'].search([('name', '=', 'video chantier.mp4')]))

    def test_refused_file_does_not_stop_the_others(self):
        self.env['ir.config_parameter'].set_param('dms.forbidden_extensions', 'exe')
        self.file('outil.exe', self.interne1, mimetype='application/x-msdownload')
        counts = self.env['bgg.documents.dms']._convert()
        self.assertEqual(counts['fichiers en erreur'], 1)
        self.assertFalse(self.env['dms.file'].search([('name', '=', 'outil.exe')]))
        self.assertTrue(self.env['dms.file'].search([('name', '=', 'facture.pdf')]))
        # allowed again: the next run moves it
        self.env['ir.config_parameter'].set_param('dms.forbidden_extensions', '')
        counts = self.env['bgg.documents.dms']._convert()
        self.assertEqual((counts.get('fichiers'), counts.get('fichiers en erreur', 0)), (1, 0))

    def test_french_name_kept(self):
        self.env['res.lang']._activate_lang('fr_BE')
        folder = self.folder('Tâches Avant - Installation')
        folder.with_context(lang='fr_BE').name = 'Projet - Client'
        self.env['bgg.documents.dms']._convert()
        self.assertTrue(self._dir('Projet - Client'))
