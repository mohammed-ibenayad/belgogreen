# -*- coding: utf-8 -*-

import collections
import logging
import math
import os

from odoo import Command, api, models

_logger = logging.getLogger(__name__)

STORAGE_NAME = 'Documents'
NO_FOLDER_NAME = 'Documents sans dossier'
TAG_CATEGORY_NAME = 'Documents'
# Document -> dms record of each converted document (makes a new run add only
# the documents created since the previous one).
MAP_TABLE = 'bgg_documents_dms_map'
# Longest name in bytes dms accepts (it checks names on the file system).
MAX_NAME_BYTES = 240
# Records saved per batch when run from the shell (commit=True).
BATCH_SIZE = 200
# Not moved: Odoo spreadsheets (no editor in Community).
SPREADSHEET_MIMETYPES = ('application/o-spreadsheet',)


def clean_name(name):
    """A name dms accepts: no "/", no NUL, not empty, not too long."""
    name = (name or '').replace('/', '-').replace('\x00', '').strip()
    if name in ('', '.', '..'):
        name = 'Sans nom'
    while len(name.encode('utf-8')) > MAX_NAME_BYTES:
        base, ext = os.path.splitext(name)
        name = (base[:-1] + ext) if len(base) > 1 else name[:-1]
    return name


def unique_name(name, taken, is_file):
    """name, or "name (2)", "name (3)"... (before the extension for files)."""
    candidate, number = name, 2
    base, ext = os.path.splitext(name) if is_file else (name, '')
    while candidate in taken:
        candidate = f"{base} ({number}){ext}"
        number += 1
    taken.add(candidate)
    return candidate


class BggDocumentsDms(models.AbstractModel):
    _name = 'bgg.documents.dms'
    _description = 'Documents (Enterprise) vers DMS'

    # ------------------------------------------------------------------
    # Source: the Documents tables, read in SQL
    # ------------------------------------------------------------------

    @api.model
    def _source_name(self, value):
        """Documents names are translatable: the French one is the one users
        see."""
        if isinstance(value, dict):
            return value.get('fr_BE') or value.get('fr_FR') or value.get('en_US') or next(iter(value.values()), '')
        return value or ''

    @api.model
    def _read_documents(self):
        cr = self.env.cr
        cr.execute("""
            SELECT d.id, d.name, d.type, d.folder_id, d.attachment_id, d.active, d.handler,
                   d.shortcut_document_id, d.access_internal, d.owner_id,
                   d.create_uid, d.create_date, d.write_uid, d.write_date, a.mimetype
              FROM documents_document d
              LEFT JOIN ir_attachment a ON a.id = d.attachment_id
             ORDER BY d.id
        """)
        columns = [c.name for c in cr.description]
        return {row[0]: dict(zip(columns, row)) for row in cr.fetchall()}

    @api.model
    def _read_access(self):
        """{document id: [(user id, role)]} for the internal users given access."""
        cr = self.env.cr
        cr.execute("""
            SELECT a.document_id, u.id, a.role
              FROM documents_access a
              JOIN res_users u ON u.partner_id = a.partner_id AND NOT u.share AND u.active
        """)
        access = collections.defaultdict(list)
        for document_id, user_id, role in cr.fetchall():
            access[document_id].append((user_id, role))
        return access

    @api.model
    def _read_tags(self):
        """{document id: [(tag id, tag name)]}; the relation table is read
        from the field definition."""
        cr = self.env.cr
        cr.execute("""SELECT relation_table, column1, column2 FROM ir_model_fields
                      WHERE model = 'documents.document' AND name = 'tag_ids'""")
        row = cr.fetchone()
        if not row or not all(row):
            return {}
        table, doc_col, tag_col = row
        cr.execute(f"""SELECT r."{doc_col}", t.id, t.name FROM "{table}" r
                       JOIN documents_tag t ON t.id = r."{tag_col}" """)
        tags = collections.defaultdict(list)
        for document_id, tag_id, name in cr.fetchall():
            tags[document_id].append((tag_id, self._source_name(name)))
        return tags

    # ------------------------------------------------------------------
    # Target: dms
    # ------------------------------------------------------------------

    @api.model
    def _storage(self):
        Storage = self.env['dms.storage']
        return Storage.search([('name', '=', STORAGE_NAME), ('save_type', '=', 'file')], limit=1) or Storage.create({
            'name': STORAGE_NAME,
            'save_type': 'file',
            'company_id': False,
        })

    @api.model
    def _access_group(self, name, write, users=None):
        """dms access group: all internal users (users=None) or the users
        given, with or without the edit rights."""
        Group = self.env['dms.access.group']
        group = Group.search([('name', '=', name)], limit=1)
        vals = {'perm_create': write, 'perm_write': write, 'perm_unlink': write}
        if users is None:
            vals['group_ids'] = [Command.set(self.env.ref('base.group_user').ids)]
        else:
            vals['explicit_user_ids'] = [Command.set(users)]
        if group:
            group.write(vals)
            return group
        return Group.create(dict(vals, name=name))

    @api.model
    def _top_folder_groups(self, top, subtree, docs, access):
        """Access of a top folder: all internal users when Documents opened
        something in it to them, else the users who had access there."""
        internal = {docs[i]['access_internal'] for i in subtree}
        if 'edit' in internal:
            return self._access_group('Documents - utilisateurs internes', True)
        if 'view' in internal:
            return self._access_group('Documents - utilisateurs internes (lecture)', False)
        users, write = set(), False
        for doc_id in subtree:
            if docs[doc_id]['owner_id']:
                users.add(docs[doc_id]['owner_id'])
            for user_id, role in access.get(doc_id, ()):
                users.add(user_id)
                write = write or role == 'edit'
        name = f"Documents - {self._source_name(top['name']).strip() or top['id']} ({top['id']})"
        return self._access_group(name, write or bool(users), sorted(users))

    def _ensure_map_table(self):
        self.env.cr.execute(f"""CREATE TABLE IF NOT EXISTS {MAP_TABLE} (
            document_id INTEGER PRIMARY KEY, directory_id INTEGER, file_id INTEGER)""")
        self.env.cr.execute(f"SELECT document_id, directory_id, file_id FROM {MAP_TABLE}")
        return {row[0]: row[1:] for row in self.env.cr.fetchall()}

    def _save_map(self, document_id, directory_id=None, file_id=None):
        self.env.cr.execute(f"INSERT INTO {MAP_TABLE} VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                            [document_id, directory_id, file_id])

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    @api.model
    def _convert(self, commit=False, batch_size=BATCH_SIZE):
        """Copy the Documents folders and files into dms. Returns counts.

        commit=True (run from the Odoo shell): saved every `batch_size`
        records and the memory cache emptied in between, so the run fits in
        the memory of an Odoo.sh shell and can be resumed if interrupted
        (converted documents are skipped)."""
        self = self.sudo().with_context(active_test=False, tracking_disable=True, mail_create_nolog=True,
                                        mail_notrack=True)
        counts = collections.Counter()
        pending = [0]

        def checkpoint(force=False):
            pending[0] += 1
            if force or pending[0] >= batch_size:
                self.env.flush_all()
                if commit:
                    self.env.cr.commit()
                    _logger.info("bgg_documents_dms: saved, %s", dict(counts))
                self.env.invalidate_all()
                pending[0] = 0

        # the Documents tables are read in SQL
        self.env.flush_all()
        done = self._ensure_map_table()
        docs = self._read_documents()
        access = self._read_access()
        children = collections.defaultdict(list)
        for doc in docs.values():
            children[doc['folder_id']].append(doc['id'])
        storage = self._storage()
        Directory = self.env['dms.directory']

        def subtree(doc_id):
            ids, stack = [], [doc_id]
            while stack:
                current = stack.pop()
                ids.append(current)
                stack.extend(children.get(current, ()))
            return ids

        def taken_names(directory, files):
            if not directory:
                return set(storage.root_directory_ids.mapped('name'))
            return set((directory.file_ids if files else directory.child_directory_ids).mapped('name'))

        # Folders, top-down
        directory_of = {doc_id: Directory.browse(ids[0]) for doc_id, ids in done.items() if ids[0]}
        taken = {}
        # top folders (and folders whose parent no longer exists)
        level = [d['id'] for d in docs.values()
                 if d['type'] == 'folder' and (not d['folder_id'] or d['folder_id'] not in docs)]
        while level:
            next_level = []
            for doc_id in level:
                doc = docs[doc_id]
                next_level += [c for c in children.get(doc_id, ()) if docs[c]['type'] == 'folder']
                if doc_id in directory_of:
                    continue
                parent = directory_of.get(doc['folder_id'], Directory) if doc['folder_id'] in docs else Directory
                key = ('dir', parent.id)
                if key not in taken:
                    taken[key] = taken_names(parent, files=False)
                vals = {'name': unique_name(clean_name(self._source_name(doc['name'])), taken[key], is_file=False)}
                if parent:
                    vals['parent_id'] = parent.id
                else:
                    vals.update({
                        'is_root_directory': True,
                        'storage_id': storage.id,
                        'group_ids': [Command.set(self._top_folder_groups(doc, subtree(doc_id), docs, access).ids)],
                    })
                try:
                    with self.env.cr.savepoint():
                        directory = Directory.create(vals)
                        self._save_map(doc_id, directory_id=directory.id)
                        self._move_messages(doc_id, directory)
                except Exception as error:  # noqa: BLE001 - one bad folder must not stop the others
                    self._failed(counts, 'dossiers en erreur', doc, error)
                    continue
                directory_of[doc_id] = directory
                counts['dossiers'] += 1
                checkpoint()
            level = next_level
        checkpoint(force=True)

        # Files
        tags = self._tag_map()
        no_folder = None
        files_by_directory = collections.defaultdict(list)
        for doc in docs.values():
            if doc['id'] in done or doc['type'] != 'binary':
                if doc['type'] == 'url':
                    counts['liens ignorés'] += 1
                continue
            if doc['shortcut_document_id']:
                counts['raccourcis ignorés'] += 1
                continue
            if doc['handler'] == 'spreadsheet' or doc['mimetype'] in SPREADSHEET_MIMETYPES:
                counts['feuilles de calcul ignorées'] += 1
                continue
            if not doc['attachment_id']:
                counts['sans fichier ignorés'] += 1
                continue
            directory = directory_of.get(doc['folder_id'])
            if not directory:
                if no_folder is None:
                    no_folder = self._no_folder_directory(storage)
                directory = no_folder
            files_by_directory[directory].append(doc)
        self._fit_max_size([doc['attachment_id'] for docs_ in files_by_directory.values() for doc in docs_])
        File = self.env['dms.file']
        for directory, directory_docs in files_by_directory.items():
            names = taken_names(directory, files=True)
            for doc in directory_docs:
                try:
                    with self.env.cr.savepoint():
                        dms_file = File.create({
                            'name': unique_name(clean_name(self._source_name(doc['name'])), names, is_file=True),
                            'directory_id': directory.id,
                            'active': doc['active'],
                            'mimetype': doc['mimetype'] or 'application/octet-stream',
                            'tag_ids': [Command.set(tags.get(doc['id'], []))],
                        })
                        self._link_stored_file(dms_file, doc)
                        self._save_map(doc['id'], file_id=dms_file.id)
                        self._move_messages(doc['id'], dms_file)
                except Exception as error:  # noqa: BLE001 - one bad file must not stop the others
                    self._failed(counts, 'fichiers en erreur', doc, error)
                    continue
                counts['fichiers'] += 1
                counts['fichiers archivés'] += not doc['active']
                checkpoint()
        checkpoint(force=True)
        self._refresh_images(checkpoint)
        self._grant_dms_rights()
        Project = self.env.get('project.project')
        if Project is not None and 'x_dms_directory_id' in Project._fields:
            counts['projets liés'] = Project._bgg_link_converted_directories()
        checkpoint(force=True)
        _logger.info("bgg_documents_dms: %s", dict(counts))
        return dict(counts)

    def _failed(self, counts, key, doc, error):
        """Logged and counted; the document is not marked as done, so the
        next run tries it again."""
        self.env.invalidate_all()
        counts[key] += 1
        _logger.warning("bgg_documents_dms: document %s %r not moved: %s",
                        doc['id'], self._source_name(doc['name']), error)

    def _fit_max_size(self, attachment_ids):
        """dms refuses files above its "max upload size" (25 MB by default);
        Documents had no limit: the setting is raised to the largest file."""
        if not attachment_ids:
            return
        self.env.cr.execute("SELECT max(file_size) FROM ir_attachment WHERE id = ANY(%s)", [attachment_ids])
        largest = self.env.cr.fetchone()[0] or 0
        limit = self.env['dms.file']._get_binary_max_size()
        needed = math.ceil(largest / 1024 / 1024)
        if needed > limit:
            self.env['ir.config_parameter'].set_param('dms.binary_max_size', needed)
            _logger.info("bgg_documents_dms: dms max upload size raised from %s to %s MB (largest file)", limit, needed)

    def _no_folder_directory(self, storage):
        Directory = self.env['dms.directory']
        directory = storage.root_directory_ids.filtered(lambda d: d.name == NO_FOLDER_NAME)[:1]
        return directory or Directory.create({
            'name': NO_FOLDER_NAME,
            'is_root_directory': True,
            'storage_id': storage.id,
            'group_ids': [Command.set(self._access_group('Documents - utilisateurs internes', True).ids)],
        })

    def _tag_map(self):
        """{document id: [dms tag ids]}, the Documents tags in use."""
        source = self._read_tags()
        if not source:
            return {}
        Category = self.env['dms.category']
        category = Category.search([('name', '=', TAG_CATEGORY_NAME), ('parent_id', '=', False)], limit=1) \
            or Category.create({'name': TAG_CATEGORY_NAME})
        Tag = self.env['dms.tag']
        dms_tags, result = {}, collections.defaultdict(list)
        for document_id, tag_list in source.items():
            for tag_id, name in tag_list:
                if tag_id not in dms_tags:
                    dms_tags[tag_id] = (Tag.search([('name', '=', name), ('category_id', '=', category.id)], limit=1)
                                        or Tag.create({'name': name, 'category_id': category.id})).id
                result[document_id].append(dms_tags[tag_id])
        return result

    def _link_stored_file(self, dms_file, doc):
        """The dms file content is an attachment of the dms file (filestore
        storage): a new attachment row on the same stored file, so nothing
        is copied and the file stays when Documents deletes its own rows.
        Author and dates of the document are kept."""
        cr = self.env.cr
        cr.execute("""
            INSERT INTO ir_attachment (name, res_model, res_field, res_id, type, store_fname, db_datas, file_size,
                                       checksum, mimetype, index_content, public, company_id,
                                       create_uid, create_date, write_uid, write_date)
            SELECT %s, 'dms.file', 'content_file', %s, a.type, a.store_fname, a.db_datas, a.file_size,
                   a.checksum, a.mimetype, a.index_content, false, NULL, %s, %s, %s, %s
              FROM ir_attachment a WHERE a.id = %s
            RETURNING file_size, checksum
        """, [dms_file.name, dms_file.id, doc['create_uid'], doc['create_date'], doc['write_uid'], doc['write_date'],
              doc['attachment_id']])
        size, checksum = cr.fetchone() or (0, None)
        dms_file.invalidate_recordset(['content', 'content_file'])
        dms_file.write({'size': size or 0, 'checksum': checksum})
        dms_file.flush_recordset()
        # dms recomputes the type from the (then empty) content: the
        # original type is put back
        cr.execute("""UPDATE dms_file SET mimetype = %s, create_uid = %s, create_date = %s, write_uid = %s,
                              write_date = %s WHERE id = %s""",
                   [doc['mimetype'] or 'application/octet-stream', doc['create_uid'], doc['create_date'],
                    doc['write_uid'], doc['write_date'], dms_file.id])
        dms_file.invalidate_recordset(['mimetype', 'create_uid', 'create_date', 'write_uid', 'write_date'])

    def _move_messages(self, document_id, record):
        self.env.cr.execute("UPDATE mail_message SET model = %s, res_id = %s WHERE model = 'documents.document' "
                            "AND res_id = %s", [record._name, record.id, document_id])

    def _refresh_images(self, checkpoint):
        """Thumbnails of the images (computed from the content, which was
        linked after the creation). One image at a time, written and
        dropped from memory before the next: the images are large."""
        file_ids = self.env['dms.file'].search([('mimetype', '=like', 'image/%'), ('image_1920', '=', False)]).ids
        for file_id in file_ids:
            dms_file = self.env['dms.file'].browse(file_id)
            try:
                with self.env.cr.savepoint():
                    dms_file._compute_image_1920()
                    dms_file.flush_recordset()
            except Exception as error:  # noqa: BLE001 - a broken image keeps its icon
                _logger.warning("bgg_documents_dms: no thumbnail for dms file %s: %s", file_id, error)
            self.env.invalidate_all()
            checkpoint()

    def _grant_dms_rights(self):
        for documents_group, dms_group in (('documents.group_documents_user', 'dms.group_dms_user'),
                                           ('documents.group_documents_manager', 'dms.group_dms_manager')):
            source = self.env.ref(documents_group, raise_if_not_found=False)
            target = self.env.ref(dms_group, raise_if_not_found=False)
            if source and target:
                target.user_ids |= source.all_user_ids if 'all_user_ids' in source._fields else source.user_ids
