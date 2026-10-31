# -*- coding: utf-8 -*-

import datetime
import logging
import urllib.parse

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .project_update import check_blocked_status_change_allowed
from .sale_order import BGG_TZ, normalize_task_name

_logger = logging.getLogger(__name__)

# Local times of day used for the admin project task dates (deadlines and
# planned starts are datetimes; the computed dates are calendar dates).
ADMIN_DEADLINE_HOUR = 17
ADMIN_START_HOUR = 8


# "Bloqué" task state (admin projects only): an open task in this state sets
# its project to Bloqué (see project.project._sync_status_from_tasks). It is
# an extra value of Odoo's task state, kept when Odoo recomputes the state
# (stage or dependency change) so that only a person can remove it.
BLOCKED_TASK_STATE = '05_blocked'
# Task changes after which the project's Bloqué / Terminé status is re-evaluated.
BLOCKED_SYNC_FIELDS = ('state', 'project_id', 'active')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    state = fields.Selection(
        selection_add=[(BLOCKED_TASK_STATE, 'Bloqué')],
        ondelete={BLOCKED_TASK_STATE: 'set default'},
    )
    # View helper for the state widget: "Bloqué" is offered on admin projects only.
    x_is_admin_dossier_project = fields.Boolean(related='project_id.x_is_admin_dossier_project')
    x_is_sss_task = fields.Boolean(related='project_id.x_is_sss_project')
    # The task's client as shown on SSS tasks (with its address): Community
    # hides the standard client field on projects that are not billable.
    x_sss_partner_id = fields.Many2one(related='partner_id', string='Client', readonly=False)
    # Planned start of a task, from Enterprise Planning (project_enterprise).
    # Declared here under the same name so its column and values stay when
    # Enterprise is uninstalled (with date_deadline as the end).
    planned_date_begin = fields.Datetime(string='Date de début', copy=False)

    def action_bgg_open_itinerary(self):
        """Route to the client's address in Google Maps (as Field Service's
        "Voir l'itinéraire")."""
        self.ensure_one()
        partner = self.partner_id
        address = ', '.join(part for part in (
            partner.street, partner.street2, ' '.join(filter(None, (partner.zip, partner.city))),
            partner.country_id.name) if part)
        if not address:
            raise ValidationError(_("Le client n'a pas d'adresse."))
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://www.google.com/maps/dir/?api=1&destination=%s' % urllib.parse.quote(address),
            'target': 'new',
        }

    @api.depends('stage_id', 'depend_on_ids.state')
    def _compute_state(self):
        """Odoo resets every open state to In Progress (or Waiting) when the
        stage or the dependencies change: a blocked task keeps Bloqué."""
        blocked = self.filtered(lambda task: task.state == BLOCKED_TASK_STATE)
        for task in blocked:
            task.state = BLOCKED_TASK_STATE
        super(ProjectTask, self - blocked)._compute_state()

    @api.constrains('state', 'project_id')
    def _check_blocked_admin_project(self):
        for task in self.filtered(lambda t: t.state == BLOCKED_TASK_STATE):
            if not task.project_id or not task.project_id._get_dossier_order():
                raise ValidationError(_(
                    "Seules les tâches des projets admin (projets liés à une commande) "
                    "peuvent être bloquées : %(task)s.", task=task.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automation rules on new tasks"""
        if any(vals.get('state') == BLOCKED_TASK_STATE for vals in vals_list):
            check_blocked_status_change_allowed(self.env)
        records = super(ProjectTask, self).create(vals_list)

        records._assign_responsable_dossier_on_create()
        records._apply_admin_dates_on_create()
        # a new open task reopens a project Terminé by its tasks; a blocked one blocks it
        records.project_id._sync_status_from_tasks()

        return records

    def write(self, vals):
        if 'state' in vals and any(
                (vals['state'] == BLOCKED_TASK_STATE) != (task.state == BLOCKED_TASK_STATE)
                for task in self):
            check_blocked_status_change_allowed(self.env)
        sync = any(fname in vals for fname in BLOCKED_SYNC_FIELDS)
        projects = self.project_id if sync else self.env['project.project']
        result = super().write(vals)
        if sync:
            (projects | self.project_id)._sync_status_from_tasks()
        return result

    def unlink(self):
        projects = self.project_id
        result = super().unlink()
        projects._sync_status_from_tasks()
        return result

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
