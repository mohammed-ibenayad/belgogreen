# -*- coding: utf-8 -*-

import datetime
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automation rules on new tasks"""
        records = super(ProjectTask, self).create(vals_list)

        for record in records:
            self._set_welcome_call_deadline(record)

        return records

    def _set_welcome_call_deadline(self, record):
        """
        Set Welcome Call Deadline - Automation Rule
        Sets the deadline for "Welcom call" tasks to 2 days after the sales order date
        """
        try:
            # Only process if this is a new record (newly created task from template)
            if not (record.create_date == record.write_date):
                return

            # Check if task name is "Welcom call" (using the exact spelling from the requirement)
            if record.name == "Welcom call":
                _logger.info("Processing Welcome call task (ID %s) for project %s",
                           record.id, record.project_id.name if record.project_id else 'N/A')

                # Try to get the sales order from multiple sources
                sale_order = None

                # First try: direct field project_sale_order_id
                if hasattr(record, 'project_sale_order_id') and record.project_sale_order_id:
                    sale_order = record.project_sale_order_id
                # Second try: through sale_line_id (standard Odoo sale_project field)
                elif hasattr(record, 'sale_line_id') and record.sale_line_id:
                    sale_order = record.sale_line_id.order_id
                # Third try: through project's sale_order_id or sale_line_id
                elif record.project_id:
                    if hasattr(record.project_id, 'sale_order_id') and record.project_id.sale_order_id:
                        sale_order = record.project_id.sale_order_id
                    elif hasattr(record.project_id, 'sale_line_id') and record.project_id.sale_line_id:
                        sale_order = record.project_id.sale_line_id.order_id

                if sale_order and hasattr(sale_order, 'date_order'):
                    order_date = sale_order.date_order

                    if order_date:
                        # Calculate deadline date (2 days after order date)
                        deadline_date = order_date + datetime.timedelta(days=2)

                        # Set the deadline to two days after the sales order date
                        record.write({
                            'date_deadline': deadline_date
                        })

                        # Log the action for tracking
                        project_name = record.project_id.name if record.project_id else 'N/A'
                        _logger.info("Welcome call deadline set to %s (2 days after order date %s) for task ID %s in project %s",
                                   deadline_date, order_date, record.id, project_name)
                    else:
                        _logger.warning("Sales order has no date_order for Welcome call task ID %s", record.id)
                else:
                    _logger.warning("No sales order linked to Welcome call task ID %s", record.id)

        except Exception as e:
            _logger.error("Set Welcome Call Deadline - Error processing task ID %s: %s",
                        record.id, str(e), exc_info=True)
