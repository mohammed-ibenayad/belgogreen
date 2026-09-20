# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

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

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automation rules on new projects"""
        records = super(ProjectProject, self).create(vals_list)

        for record in records:
            self._update_project_folder_name(record)
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
                record._apply_admin_project_dates(*dates)

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

    def _apply_admin_project_dates(self, date_start, date_end):
        """Set the project start/end dates and align the deadline of the open
        tasks on the end date. Runs in sudo (side effect of the sale order)."""
        projects = self.sudo()
        projects.write({'date_start': date_start, 'date': date_end})
        _logger.info("Dossier: admin project dates %s -> %s set on projects %s",
                     date_start, date_end, projects.ids)
        open_tasks = self.env['project.task'].sudo().search([
            ('project_id', 'in', projects.ids),
            ('state', 'not in', ['1_done', '1_canceled']),
        ])
        open_tasks._apply_admin_deadline(date_end)

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
        """Override write to handle folder creation after project creation"""
        self._check_admin_project_locked_fields(vals)
        result = super(ProjectProject, self).write(vals)

        # If a documents folder is being added to the project, try to rename it
        if 'documents_folder_id' in vals and vals['documents_folder_id']:
            _logger.info("[FOLDER RENAME] documents_folder_id added via write(), triggering rename")
            for record in self:
                # Force the rename since this might be adding the folder after creation
                self._update_project_folder_name(record, force=True)

        return result

    def _update_project_folder_name(self, record, force=False):
        """
        Update Project Folder Name - Automation Rule
        Renames the project's documents folder based on sales order and customer name
        Format: SO Name - Projet - Customer Name

        Args:
            record: project.project record
            force: if True, skip the timestamp check (useful for manual triggers)
        """
        try:
            _logger.info("[FOLDER RENAME] Checking project (ID %s): %s", record.id, record.name)
            _logger.info("[FOLDER RENAME]   create_date: %s, write_date: %s",
                        record.create_date, record.write_date)

            # Only process if this is a new record (newly created project from template)
            # Skip this check if force=True (for manual triggers)
            if not force and not (record.create_date == record.write_date):
                _logger.info("[FOLDER RENAME]   Skipping - not a new record (create_date != write_date)")
                return

            # Check if project has an associated sale order line
            if not record.sale_line_id:
                _logger.info("[FOLDER RENAME]   Skipping - no sale_line_id")
                return

            # Get the sales order and client information
            sale_order = record.sale_line_id.order_id
            customer = sale_order.partner_id

            _logger.info("[FOLDER RENAME]   Sale Order: %s, Customer: %s",
                        sale_order.name, customer.name)

            # Check if we have a documents folder created
            if not record.documents_folder_id:
                _logger.info("[FOLDER RENAME]   Skipping - no documents folder yet for project ID %s", record.id)
                return

            # Create new folder name with SO reference and client name
            new_folder_name = f"{sale_order.name} - Projet - {customer.name}"
            current_folder_name = record.documents_folder_id.name

            _logger.info("[FOLDER RENAME]   Current folder: '%s'", current_folder_name)
            _logger.info("[FOLDER RENAME]   Target folder: '%s'", new_folder_name)

            if current_folder_name != new_folder_name:
                record.documents_folder_id.write({
                    'name': new_folder_name
                })
                _logger.info("[FOLDER RENAME]   ✓ Updated folder name to: '%s' for project ID %s",
                           new_folder_name, record.id)
            else:
                _logger.info("[FOLDER RENAME]   Folder name already correct for project ID %s", record.id)

        except Exception as e:
            _logger.error("[FOLDER RENAME] Error processing project ID %s: %s",
                        record.id, str(e), exc_info=True)
