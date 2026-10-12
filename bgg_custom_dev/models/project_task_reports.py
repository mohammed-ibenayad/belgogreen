# -*- coding: utf-8 -*-

from odoo import fields, models

# The task reports copy the task state selection: add the "Bloqué" state of
# project_task.py so blocked tasks are labelled there too.


class ReportProjectTaskUser(models.Model):
    _inherit = 'report.project.task.user'

    state = fields.Selection(selection_add=[('05_blocked', 'Bloqué')])


class ProjectTaskBurndownChartReport(models.AbstractModel):
    _inherit = 'project.task.burndown.chart.report'

    state = fields.Selection(selection_add=[('05_blocked', 'Bloqué')])
