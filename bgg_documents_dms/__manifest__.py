# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen - Documents vers DMS',
    'version': '19.0.1.0.0',
    'category': 'Customizations',
    'summary': 'One-off move of the Enterprise Documents into OCA dms before Documents is uninstalled',
    'description': """
        Documents (Enterprise) -> OCA dms
        =================================

        Installed on Odoo.sh at migration time, next to Documents and OCA dms.
        The installation copies every Documents folder and file into dms, in
        the same database; Documents can then be uninstalled (this module goes
        with it, the dms content stays).

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
        - Not moved: spreadsheets, link documents, shortcuts.

        Running the conversion again (button in Settings > Technical, or
        env['bgg.documents.dms']._convert()) only adds the documents created
        since the last run.
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
    'post_init_hook': 'post_init',
    'installable': True,
    'application': False,
    'auto_install': False,
}
