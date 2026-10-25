# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .sale_order import RESPONSABLE_DOSSIER_ADMIN_GROUP, RESPONSABLE_DOSSIER_GROUP

# "Bloqué" status of the admin projects (Dossier): set manually through a
# project status update, or automatically while one of the project's tasks is
# blocked (project_task.py), counted by the AMSS Management dashboard. French
# business wording on purpose. Red dot, as "Off Track" (see STATUS_COLOR in
# project/models/project_update.py).
BLOCKED_STATUS = 'blocked'
BLOCKED_STATUS_COLOR = 23


def user_can_manage_blocked_status(env):
    """Members of Responsable Dossier (or Responsable Dossier Admin) may set
    or remove the Bloqué status of a project or a task; automations (sudo)
    are not restricted."""
    return (env.su
            or env.user.has_group(RESPONSABLE_DOSSIER_GROUP)
            or env.user.has_group(RESPONSABLE_DOSSIER_ADMIN_GROUP))


def check_blocked_status_change_allowed(env):
    if not user_can_manage_blocked_status(env):
        raise AccessError(_(
            "Seuls les membres du groupe « Responsable Dossier » peuvent mettre "
            "un projet ou une tâche au statut « Bloqué » ou le retirer de ce statut."
        ))


class ProjectUpdate(models.Model):
    _inherit = 'project.update'

    status = fields.Selection(
        selection_add=[('on_hold',), (BLOCKED_STATUS, 'Bloqué')],
        ondelete={BLOCKED_STATUS: lambda updates: updates.write({'status': 'off_track'})},
    )

    # A project whose automatic status (Bloqué / Terminé from its tasks) is
    # undone while it had no status before goes back to "no status" (Odoo
    # cannot post a status update without a status): that update stays in
    # the history with this date, so the dashboard knows when it ended (see
    # amss_dashboard._blocked_projects).
    x_unblocked_on = fields.Date(string='Statut retiré le (retour sans statut)', readonly=True, copy=False)

    @api.depends('status')
    def _compute_color(self):
        blocked = self.filtered(lambda u: u.status == BLOCKED_STATUS)
        blocked.color = BLOCKED_STATUS_COLOR
        super(ProjectUpdate, self - blocked)._compute_color()

    @api.constrains('status', 'project_id')
    def _check_blocked_status_admin_project(self):
        for update in self.filtered(lambda u: u.status == BLOCKED_STATUS):
            if not update.project_id._get_dossier_order():
                raise ValidationError(_(
                    "Le statut « Bloqué » est réservé aux projets admin (projets "
                    "liés à une commande) : %(project)s n'en est pas un.",
                    project=update.project_id.display_name,
                ))

    @api.model
    def _check_no_blocked_task(self, project):
        """A project cannot leave the Bloqué status while one of its open
        tasks is blocked."""
        tasks = project._blocked_open_tasks()
        if tasks:
            raise UserError(_(
                "Le projet « %(project)s » ne peut pas quitter le statut « Bloqué » : "
                "des tâches sont bloquées (%(tasks)s). Débloquez-les d'abord.",
                project=project.display_name,
                tasks=', '.join(tasks.mapped('name')),
            ))

    @api.model_create_multi
    def create(self, vals_list):
        # A new update either sets Bloqué or, on a blocked project, removes it.
        Project = self.env['project.project']
        for vals in vals_list:
            project_id = vals.get('project_id') or self.env.context.get('default_project_id')
            project = Project.browse(project_id).exists() if project_id else Project
            was_blocked = project.last_update_status == BLOCKED_STATUS
            sets_blocked = vals.get('status') == BLOCKED_STATUS
            if sets_blocked != was_blocked:
                check_blocked_status_change_allowed(self.env)
            if was_blocked and not sets_blocked and project:
                self._check_no_blocked_task(project)
        updates = super().create(vals_list)
        # Once the project leaves Bloqué, it is no longer blocked by its tasks.
        updates.filtered(lambda u: u.status != BLOCKED_STATUS).project_id.sudo().filtered(
            'x_blocked_by_task').write({'x_blocked_by_task': False})
        # ... and once it leaves Terminé, it is no longer Terminé by its tasks.
        updates.filtered(lambda u: u.status != 'done').project_id.sudo().filtered(
            'x_done_by_tasks').write({'x_done_by_tasks': False})
        return updates

    def write(self, vals):
        if 'status' in vals and any(
                (vals['status'] == BLOCKED_STATUS) != (update.status == BLOCKED_STATUS)
                for update in self):
            check_blocked_status_change_allowed(self.env)
            if vals['status'] != BLOCKED_STATUS:
                for update in self.filtered(lambda u: u.status == BLOCKED_STATUS):
                    self._check_no_blocked_task(update.project_id)
        return super().write(vals)

    def unlink(self):
        if any(update.status == BLOCKED_STATUS for update in self):
            check_blocked_status_change_allowed(self.env)
            for update in self.filtered(lambda u: u.status == BLOCKED_STATUS):
                if update.project_id.last_update_id == update:
                    self._check_no_blocked_task(update.project_id)
        return super().unlink()
