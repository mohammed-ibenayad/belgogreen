# -*- coding: utf-8 -*-

import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automation rules on new projects"""
        records = super(ProjectProject, self).create(vals_list)

        for record in records:
            self._update_project_folder_name(record)

        return records

    def write(self, vals):
        """Override write to handle folder creation after project creation"""
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
                _logger.warning("[FOLDER RENAME]   No documents folder found for project ID %s", record.id)
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
