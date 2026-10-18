# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

from .project_update import BLOCKED_STATUS, BLOCKED_STATUS_COLOR

_logger = logging.getLogger(__name__)

# Fields of an admin project (project linked to a sale order) that are computed
# from the order (Responsable du dossier, payment term x product categories)
# and therefore locked against manual edits.
ADMIN_PROJECT_LOCKED_FIELDS = ('user_id', 'date_start', 'date')


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # View helper: True for admin projects (linked to a sale order), on which
    # the project manager and the planned dates are read-only in the form.
    x_is_admin_dossier_project = fields.Boolean(
        string='Admin Project (Dossier)',
        compute='_compute_is_admin_dossier_project',
        compute_sudo=True,
    )

    @api.depends('sale_line_id', 'reinvoiced_sale_order_id')
    def _compute_is_admin_dossier_project(self):
        for project in self:
            project.x_is_admin_dossier_project = bool(project._get_dossier_order())

    # "Bloqué" status (admin projects only, see project_update.py). Setting
    # the status from the project creates a status update, where the checks
    # are made.
    # Field service (SSS) project of an order. Own flag replacing the
    # Enterprise Field Service 'is_fsm' (kept in sync by the bridge module
    # bgg_custom_dev_ee while Enterprise is installed).
    x_is_sss_project = fields.Boolean(
        string='Projet SSS (service sur site)',
        index=True,
        copy=False,
    )

    last_update_status = fields.Selection(
        selection_add=[('on_hold',), (BLOCKED_STATUS, 'Bloqué')],
        ondelete={BLOCKED_STATUS: 'set default'},
    )

    @api.depends('last_update_status')
    def _compute_last_update_color(self):
        blocked = self.filtered(lambda p: p.last_update_status == BLOCKED_STATUS)
        blocked.last_update_color = BLOCKED_STATUS_COLOR
        super(ProjectProject, self - blocked)._compute_last_update_color()

    # Technical: the project was set to Bloqué automatically because one of
    # its tasks is blocked (task state "Bloqué", see project_task.py). Only such a project
    # gets its previous status back once no task is blocked any more; a
    # project blocked by hand stays blocked.
    x_blocked_by_task = fields.Boolean(string='Bloqué par une tâche', copy=False, readonly=True)
    # Technical: the project was set to Terminé automatically because all its
    # tasks are closed. Only such a project leaves Terminé by itself when a
    # task is reopened or added; a project set to Terminé by hand stays so.
    x_done_by_tasks = fields.Boolean(string='Terminé par les tâches', copy=False, readonly=True)

    def _blocked_open_tasks(self):
        return self.env['project.task'].sudo().search([
            ('project_id', 'in', self.ids),
            ('state', '=', '05_blocked'),
        ])

    def _post_status_update(self, status, description=None):
        """Post a status update (automation, sudo)."""
        self.ensure_one()
        vals = {
            'name': 'Mise à jour du statut - %s' % fields.Date.context_today(self).strftime('%d/%m/%Y'),
            'project_id': self.id,
            'status': status,
        }
        if description:
            vals['description'] = description
        return self.env['project.update'].sudo().with_context(default_project_id=self.id).create(vals)

    def _restore_previous_status(self, left_status, message):
        """Give back to this project the status it had before `left_status`
        (the last update with another status), or "no status" when it had
        none: the current update is then kept in the history, marked with the
        date it was left (x_unblocked_on), and a chatter message is posted."""
        self.ensure_one()
        previous = self.env['project.update'].sudo().search([
            ('project_id', '=', self.id),
            ('status', '!=', left_status),
        ], order='date desc, id desc', limit=1)
        if previous:
            self._post_status_update(previous.status, description='<p>%s</p>' % message)
        else:
            self.last_update_id.x_unblocked_on = fields.Date.context_today(self)
            self.last_update_id = False
            self.message_post(body='%s (retour sans statut, comme avant).' % message)

    def _sync_status_from_tasks(self):
        """Admin projects follow their tasks (automation, sudo):
        - Terminé once every task is closed (done or cancelled, at least one
          done); the previous status back when a task is reopened or added;
        - Bloqué as soon as an open task is blocked; the previous status back
          once no task is blocked any more.
        Only automatic statuses are undone automatically."""
        Task = self.env['project.task'].sudo()
        for project in self.sudo().exists():
            if project.is_template or not project._get_dossier_order():
                continue
            # Terminé from the tasks
            tasks = Task.search([('project_id', '=', project.id)])
            all_closed = bool(tasks) and all(t.state in ('1_done', '1_canceled') for t in tasks) \
                and any(t.state == '1_done' for t in tasks)
            if (all_closed and project.last_update_status not in ('done', BLOCKED_STATUS)):
                project._post_status_update('done', description=(
                    '<p>Terminé automatiquement : toutes les tâches sont closes.</p>'))
                project.x_done_by_tasks = True
                _logger.info("Dossier: project %s done (all tasks closed)", project.id)
            elif not all_closed and project.x_done_by_tasks:
                project._restore_previous_status(
                    'done', 'Rouvert automatiquement : une tâche est de nouveau ouverte')
                project.x_done_by_tasks = False
                _logger.info("Dossier: project %s reopened (open task)", project.id)
            # Bloqué from the tasks
            blocked_tasks = project._blocked_open_tasks()
            if blocked_tasks and project.last_update_status != BLOCKED_STATUS:
                project._post_status_update(BLOCKED_STATUS, description=(
                    '<p>Bloqué automatiquement : tâche(s) bloquée(s) : %s.</p>'
                    % ', '.join(blocked_tasks.mapped('name'))))
                project.x_blocked_by_task = True
                _logger.info("Dossier: project %s blocked by tasks %s", project.id, blocked_tasks.ids)
            elif not blocked_tasks and project.x_blocked_by_task:
                project._restore_previous_status(
                    BLOCKED_STATUS, 'Débloqué automatiquement : plus aucune tâche bloquée')
                project.x_blocked_by_task = False
                _logger.info("Dossier: project %s unblocked (no blocked task)", project.id)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automation rules on new projects"""
        records = super(ProjectProject, self).create(vals_list)

        for record in records:
            # Dossier: a project created for an order that already has a
            # Responsable gets them as project manager. Its tasks do not exist
            # yet at this point (template tasks are copied after the project
            # is created): they are handled in project.task.create.
            responsable = record._get_responsable_dossier()
            if responsable:
                record._apply_responsable_dossier(responsable)
            # Dossier: admin project deadlines from the order's payment term and
            # product categories (tasks get their deadline in project.task.create).
            order = record._get_dossier_order()
            dates = order._compute_admin_project_dates() if order else None
            if dates:
                record._apply_admin_project_dates(
                    *dates, task_dates=order._compute_admin_task_dates())

        return records

    def _check_admin_project_locked_fields(self, vals):
        """Block manual edits of the project manager and the planned dates on
        admin projects: they are computed from the sale order (Responsable du
        dossier, payment term x product categories). The automations write
        them in sudo and are not affected; a re-sent unchanged value is not a
        change."""
        if self.env.su:
            return
        touched = [f for f in ADMIN_PROJECT_LOCKED_FIELDS if f in vals]
        if not touched:
            return
        for project in self:
            order = project._get_dossier_order()
            if not order:
                continue
            changed = []
            for fname in touched:
                new = vals[fname]
                if fname == 'user_id':
                    current = project.user_id.id
                    new = new or False
                else:
                    current = project[fname]
                    new = fields.Date.to_date(new) if new else False
                if new != current:
                    changed.append(fname)
            if changed:
                labels = ', '.join(
                    '« %s »' % project._fields[f]._description_string(self.env)
                    for f in changed)
                raise UserError(
                    "Le projet « %s » est lié à la commande %s : le chef de projet "
                    "et les dates planifiées sont calculés automatiquement "
                    "(Responsable du dossier, conditions de paiement) et ne peuvent "
                    "pas être modifiés manuellement (%s)."
                    % (project.display_name, order.name, labels))

    def _apply_admin_project_dates(self, date_start, date_end, task_dates=None):
        """Set the project start/end dates and the dates of the open tasks:
        tasks listed in `task_dates` ({normalized name: (start, deadline)},
        the ones following the SSS reference dates) get those dates, every
        other open task gets the project end date as deadline. Runs in sudo
        (side effect of the sale order)."""
        projects = self.sudo()
        projects.write({'date_start': date_start, 'date': date_end})
        _logger.info("Dossier: admin project dates %s -> %s set on projects %s",
                     date_start, date_end, projects.ids)
        open_tasks = self.env['project.task'].sudo().search([
            ('project_id', 'in', projects.ids),
            ('state', 'not in', ['1_done', '1_canceled']),
        ])
        open_tasks._apply_admin_dates(date_end, task_dates or {})

    # ------------------------------------------------------------------
    # Dossier: Responsable of the linked sale order
    # ------------------------------------------------------------------

    def _get_dossier_order(self):
        """Sale order this project belongs to (sale_project links), if any."""
        self.ensure_one()
        project = self.sudo()
        return project.reinvoiced_sale_order_id or project.sale_line_id.order_id

    def _get_responsable_dossier(self):
        """Responsable of the linked sale order (empty recordset if none)."""
        self.ensure_one()
        order = self._get_dossier_order()
        return order.x_responsable_dossier_id if order else self.env['res.users']

    def _apply_responsable_dossier(self, responsable, previous_user=None):
        """Make `responsable` the project manager of these projects and an
        assignee of their open tasks. `previous_user` (the former Responsable)
        is unassigned from those tasks. Runs in sudo: this is a side effect of
        editing the sale order, whose author may not manage projects.
        """
        projects = self.sudo()
        if responsable:
            to_update = projects.filtered(lambda p: p.user_id != responsable)
            if to_update:
                to_update.write({'user_id': responsable.id})
                _logger.info("Dossier: Responsable %s set as project manager on projects %s",
                             responsable.name, to_update.ids)
        open_tasks = self.env['project.task'].sudo().search([
            ('project_id', 'in', projects.ids),
            ('state', 'not in', ['1_done', '1_canceled']),
        ])
        open_tasks._apply_responsable_dossier(responsable, previous_user)

    def write(self, vals):
        """Block manual edits of the locked admin project fields"""
        self._check_admin_project_locked_fields(vals)
        return super(ProjectProject, self).write(vals)
