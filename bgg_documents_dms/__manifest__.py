# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen - Documents vers DMS',
    'version': '19.0.1.2.0',
    'category': 'Customizations',
    'summary': 'One-off move of the Enterprise Documents into OCA dms before Documents is uninstalled',
    'description': """
        Documents (Enterprise) -> OCA dms
        =================================

        Installed on Odoo.sh at migration time, next to Documents and OCA dms;
        the copy is then run from the Odoo shell (saved every 200 records, so
        it fits in the shell's memory and can be resumed):

            env['bgg.documents.dms']._convert(commit=True)

        It copies every Documents folder and file into dms, in the same
        database; Documents can then be uninstalled (this module goes with
        it, the dms content stays).

        - Storage "Documents" (filestore, all companies).
        - Folders -> directories, same tree. Names: French name kept, "/"
          replaced, made unique in their folder (" (2)"). Files without a
          folder go to "Documents sans dossier".
        - Files -> dms files on the same stored file (nothing copied, the
          file survives the removal of Documents). Archived files stay
          archived; author, dates, tags (used ones) and chatter messages kept.
        - Access per top folder: all internal users (edit, or read only) when
          Documents opened something in it to them, otherwise the users who
          had access to it. Documents users get the dms user right (managers:
          dms manager).
        - Employee folders (with a "Contrat" / "Fiche de paie" sub-folder) are
          grouped under one "RH" top folder, each keeping its own access.
        - Not moved: spreadsheets, link documents, shortcuts.
        - The dms "max upload size" is raised to the largest file (Documents
          had no limit). A document dms refuses is logged ("not moved") and
          counted, the others are moved; the next run tries it again.

        Running the conversion again only adds the documents created since the
        last run (and retries the refused ones).
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': [
        'documents',
        'dms',
    ],
    'data': [
        'data/server_actions.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
