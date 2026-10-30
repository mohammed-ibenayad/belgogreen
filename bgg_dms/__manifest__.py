# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen - DMS',
    'version': '19.0.1.3.0',
    'category': 'Document Management',
    'summary': 'DMS access groups include the users who get an Odoo group through their roles',
    'description': """
        BelGoGreen adjustments to OCA dms
        =================================

        - A DMS access group given an Odoo group (e.g. "Internal User") grants
          access to every user in that group, including the users who get it
          through another group (in Odoo 19 most internal users are "Internal
          User" that way). OCA dms only counts the users put directly in the
          group. The member lists are refreshed when users or groups change.

        - Searching files by name also matches the folders above them:
          "S00466" finds every file of the S00466 project folders, their
          sub-folders included. File cards and the list show the folder of
          each file.

        - A folder or a file can belong to a company ("Société du dossier"),
          like in Enterprise Documents. Empty, it takes the company of the
          folder above (or of the storage). The company switcher then shows
          only the folders of the selected companies, plus the folders shared
          by all companies.

        Installed automatically with dms.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': ['dms'],
    'data': ['views/dms_file_views.xml', 'views/dms_company_views.xml'],
    'post_init_hook': 'post_init',
    'installable': True,
    'application': False,
    'auto_install': True,
}
