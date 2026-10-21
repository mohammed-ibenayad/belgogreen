# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen - DMS projets',
    'version': '19.0.1.0.2',
    'category': 'Document Management',
    'summary': 'Each project has its DMS folder and a Documents button, as with Enterprise Documents',
    'description': """
        Project folders in OCA dms
        ==========================

        As Enterprise Documents (documents_project) did:

        - each project is linked to its DMS folder (field "Dossier documents"),
          with a "Documents" button on the project opening its files;
        - a new project gets its folder, under the "Projets" / "Projects" folder (or the
          folder set in the system parameter bgg_dms_project.parent_directory,
          name or id); a project created from a template also gets the
          template folder's sub-folders (empty);
        - the projects moved from Enterprise Documents are linked to their
          folder (bgg_documents_dms), at installation and after each copy.

        Installed automatically with dms and project.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': ['dms', 'project'],
    'data': ['views/project_project_views.xml'],
    'post_init_hook': 'post_init',
    'installable': True,
    'application': False,
    'auto_install': True,
}
