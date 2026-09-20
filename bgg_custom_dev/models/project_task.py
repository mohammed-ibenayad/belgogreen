# -*- coding: utf-8 -*-

import datetime
import logging

import pytz

from odoo import api, models

from .sale_order import BGG_TZ

_logger = logging.getLogger(__name__)

# Local time of day at which an admin project task deadline is set
# (deadlines are datetimes; the project end date is a date).
ADMIN_DEADLINE_HOUR = 17


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automation rules on new tasks"""
        records = super(ProjectTask, self).create(vals_list)

        records._assign_responsable_dossier_on_create()
        records._apply_admin_deadline_on_create()

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
    # Dossier: task deadline = end date of the admin project
    # ------------------------------------------------------------------

    @api.model
    def _admin_deadline_datetime(self, date_end):
        """Deadline datetime (UTC, naive) for a project end date: that day at
        ADMIN_DEADLINE_HOUR in the business timezone."""
        local = pytz.timezone(BGG_TZ).localize(
            datetime.datetime.combine(date_end, datetime.time(ADMIN_DEADLINE_HOUR, 0)))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def _apply_admin_deadline(self, date_end):
        """Set the deadline of these tasks to the project end date."""
        deadline = self._admin_deadline_datetime(date_end)
        to_update = self.sudo().filtered(lambda t: t.date_deadline != deadline)
        if to_update:
            to_update.write({'date_deadline': deadline})
            _logger.info("Dossier: deadline %s set on tasks %s", deadline, to_update.ids)

    def _apply_admin_deadline_on_create(self):
        """A task created in a project linked to a sale order takes the
        project's end date as deadline (template tasks copied on order
        confirmation, and tasks added to the project later)."""
        for project, tasks in self.grouped('project_id').items():
            if not project or not project.date or not project._get_dossier_order():
                continue
            tasks._apply_admin_deadline(project.date)
