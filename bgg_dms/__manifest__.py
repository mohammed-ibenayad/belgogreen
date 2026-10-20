# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen - DMS',
    'version': '19.0.1.0.0',
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

        Installed automatically with dms.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': ['dms'],
    'post_init_hook': 'post_init',
    'installable': True,
    'application': False,
    'auto_install': True,
}
