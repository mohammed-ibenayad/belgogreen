# -*- coding: utf-8 -*-
"""Stages added by mistake to the SSS projects (19.0.2.3.0).

An SSS project has two stages, "SSS: À faire" and "SSS: Encours/Fait".
Columns added by hand in the Field Service kanban created more stages
("Nouveau", and "Planifié", "En cours", "Terminé", "Annulé"), linked to
every SSS project, so each SSS task showed eight "Nouveau" stages. This
script:

- gives the SSS projects that miss them their two SSS stages (older
  projects made in Field Service had only the stages added there);
- moves the SSS tasks of a "Nouveau" stage to the "SSS: À faire" stage of
  their project (a new task, not started);
- takes the other stages off the SSS projects when no SSS task is in them;
- deletes those stages when no project and no task use them any more.

A stage still holding SSS tasks (other than "Nouveau") is left and logged.
In SQL, so no automation or stage-change date is triggered. Safe to run
several times.
"""
from odoo import SUPERUSER_ID, api
from odoo.tools import sql

from odoo.addons.bgg_custom_dev.hooks import fix_sss_stages


def migrate(cr, version):
    if not version or not sql.column_exists(cr, 'project_project', 'x_is_sss_project'):
        return
    fix_sss_stages(api.Environment(cr, SUPERUSER_ID, {}))
