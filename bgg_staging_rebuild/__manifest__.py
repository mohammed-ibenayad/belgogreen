# -*- coding: utf-8 -*-
{
    'name': 'BelGoGreen — Reconstruction Staging',
    'version': '19.0.1.3.0',
    'category': 'Customizations',
    'summary': 'Permet aux administrateurs de reconstruire l\'environnement Staging depuis Odoo',
    'description': """
        BelGoGreen Staging Rebuild
        ==========================

        Lets a privileged business user rebuild the Odoo.sh staging environment
        without giving them access to GitHub or the Odoo.sh dashboard.

        How it works:
        - A wizard exposes a "Rebuild Staging" button.
        - On click, the module calls the GitHub API with a stored token to either:
            * fast-forward the staging branch onto production (refresh strategy), or
            * push an empty commit on staging (no-op rebuild strategy).
        - Odoo.sh detects the push on the watched branch and rebuilds.

        Configuration is stored in System Parameters (ir.config_parameter):
            bgg_staging_rebuild.github_owner
            bgg_staging_rebuild.github_repo
            bgg_staging_rebuild.github_token        (sensitive, fill in manually)
            bgg_staging_rebuild.staging_branch      (default: main-staging)
            bgg_staging_rebuild.production_branch   (default: main)
            bgg_staging_rebuild.strategy            (refresh | empty_commit)
            bgg_staging_rebuild.cooldown_minutes    (default: 5)
            bgg_staging_rebuild.staging_url         (link to the Odoo.sh
                                                     project's builds list,
                                                     surfaced from each log)

        Build progress is read from GitHub commit statuses (Odoo.sh writes
        them when the project's "GitHub commit statuses" token is configured
        in Odoo.sh project settings). A 1-min cron + a manual Refresh button
        keep the log up to date. Odoo.sh does not expose the per-build
        instance URL via GitHub for this project, so the log links to the
        Odoo.sh builds list where the user picks the latest build.

        Every trigger is logged in bgg.staging.rebuild.log for audit.
    """,
    'author': 'BelGoGreen',
    'website': 'https://www.belgogreen.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'data/ir_cron_data.xml',
        'views/staging_rebuild_log_views.xml',
        'wizard/staging_rebuild_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
