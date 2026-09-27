# -*- coding: utf-8 -*-

import datetime
import logging

import pytz

from odoo import api, models

from .sale_order import BGG_TZ, normalize_task_name

_logger = logging.getLogger(__name__)

# Local times of day used for the admin project task dates (deadlines and
# planned starts are datetimes; the computed dates are calendar dates).
ADMIN_DEADLINE_HOUR = 17
ADMIN_START_HOUR = 8


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automation rules on new tasks"""
        records = super(ProjectTask, self).create(vals_list)

        records._assign_responsable_dossier_on_create()
        records._apply_admin_dates_on_create()

        return records

    # ------------------------------------------------------------------
    # Dossier: Responsable of the linked sale order
    # ------------------------------------------------------------------

    def _assign_responsable_dossier_on_create(self):
        """A task created in a project linked to a sale order with a
        Responsable gets the Responsable as assignee. This also covers the
        template tasks copied when the project is created on order
        confirmation, which happens after project.project.create."""
        for project, tasks in self.grouped('project_id').items():
            if not project:
                continue
            responsable = project._get_responsable_dossier()
            if responsable:
                tasks._apply_responsable_dossier(responsable)

    def _apply_responsable_dossier(self, responsable, previous_user=None):
        """Add `responsable` to the assignees of these tasks and remove
        `previous_user` (the former Responsable) from them. Existing
        assignees (the admins doing the work) are kept."""
        for task in self.sudo():
            commands = []
            if previous_user and previous_user != responsable and previous_user in task.user_ids:
                commands.append((3, previous_user.id))
            if responsable and responsable not in task.user_ids:
                commands.append((4, responsable.id))
            if commands:
                task.write({'user_ids': commands})
        if responsable:
            _logger.info("Dossier: Responsable %s assigned on tasks %s",
                         responsable.name, self.ids)

    # ------------------------------------------------------------------
    # Dossier: task dates of the admin project
    # ------------------------------------------------------------------

    @api.model
    def _admin_local_datetime(self, date, hour):
        """`date` at `hour` o'clock in the business timezone, as the naive
        UTC datetime Odoo stores."""
        local = pytz.timezone(BGG_TZ).localize(
            datetime.datetime.combine(date, datetime.time(hour, 0)))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _admin_deadline_datetime(self, date_end):
        """Deadline datetime for a computed end date (ADMIN_DEADLINE_HOUR)."""
        return self._admin_local_datetime(date_end, ADMIN_DEADLINE_HOUR)

    def _apply_admin_dates(self, project_end, task_dates):
        """Set the dates of these tasks. A task whose name matches an entry of
        `task_dates` ({normalized name: (start, deadline)}, the admin tasks
        following the SSS reference dates) gets that deadline and, when the
        planning feature is installed, that planned start. Every other task
        gets the project end date as deadline."""
        has_planned_start = 'planned_date_begin' in self._fields
        for task in self.sudo():
            rule = task_dates.get(normalize_task_name(task.name))
            vals = {}
            if rule:
                start, end = rule
                deadline = self._admin_deadline_datetime(end)
                if has_planned_start:
                    begin = self._admin_local_datetime(start, ADMIN_START_HOUR)
                    if task.planned_date_begin != begin:
                        vals['planned_date_begin'] = begin
            else:
                deadline = self._admin_deadline_datetime(project_end)
            if task.date_deadline != deadline:
                vals['date_deadline'] = deadline
            if vals:
                task.write(vals)
                _logger.info("Dossier: dates %s set on task %s (%s)", vals, task.id, task.name)

    def _apply_admin_dates_on_create(self):
        """A task created in a dated project linked to a sale order takes its
        dates from the order's rules: the SSS-based dates when its name is
        listed there, the project end date otherwise. Covers the template
        tasks copied on order confirmation and tasks added later."""
        for project, tasks in self.grouped('project_id').items():
            if not project or not project.date:
                continue
            order = project._get_dossier_order()
            if not order:
                continue
            tasks._apply_admin_dates(project.date, order._compute_admin_task_dates())
