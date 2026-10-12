# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .sale_order import RESPONSABLE_DOSSIER_ADMIN_GROUP, RESPONSABLE_DOSSIER_GROUP

# "Bloqué" status of the admin projects (Dossier): set manually through a
# project status update, counted by the AMSS Management dashboard. French
# business wording on purpose. Red dot, as "Off Track" (see STATUS_COLOR in
# project/models/project_update.py).
BLOCKED_STATUS = 'blocked'
BLOCKED_STATUS_COLOR = 23


def user_can_manage_blocked_status(env):
    """Members of Responsable Dossier (or Responsable Dossier Admin) may set
    or remove the Bloqué status; automations (sudo) are not restricted."""
    return (env.su
            or env.user.has_group(RESPONSABLE_DOSSIER_GROUP)
            or env.user.has_group(RESPONSABLE_DOSSIER_ADMIN_GROUP))


class ProjectUpdate(models.Model):
    _inherit = 'project.update'

    status = fields.Selection(
        selection_add=[('on_hold',), (BLOCKED_STATUS, 'Bloqué')],
        ondelete={BLOCKED_STATUS: lambda updates: updates.write({'status': 'off_track'})},
    )

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

    def _check_blocked_status_change_allowed(self):
        if not user_can_manage_blocked_status(self.env):
            raise AccessError(_(
                "Seuls les membres du groupe « Responsable Dossier » peuvent "
                "mettre un projet au statut « Bloqué » ou le retirer de ce statut."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        # A new update either sets Bloqué or, on a blocked project, removes it.
        Project = self.env['project.project']
        for vals in vals_list:
            project_id = vals.get('project_id') or self.env.context.get('default_project_id')
            project = Project.browse(project_id).exists() if project_id else Project
            was_blocked = project.last_update_status == BLOCKED_STATUS
            if (vals.get('status') == BLOCKED_STATUS) != was_blocked:
                self._check_blocked_status_change_allowed()
        return super().create(vals_list)

    def write(self, vals):
        if 'status' in vals and any(
                (vals['status'] == BLOCKED_STATUS) != (update.status == BLOCKED_STATUS)
                for update in self):
            self._check_blocked_status_change_allowed()
        return super().write(vals)

    def unlink(self):
        if any(update.status == BLOCKED_STATUS for update in self):
            self._check_blocked_status_change_allowed()
        return super().unlink()
