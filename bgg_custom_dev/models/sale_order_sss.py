# -*- coding: utf-8 -*-
"""'Créer tâches SSS': field service (SSS) project and tasks for paid orders.

Port of the server action of the same name that lived in the database. The
behaviour is kept as it was, message for message, with ONE change: the
project manager of the created SSS project is the user configured in the
bgg.sss_project_manager_login system parameter (it used to be left empty).
Existing SSS projects are never touched: this only runs on creation.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

SSS_ACTION_NAME = 'Créer tâches SSS'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # Logging: same destination as the server action's log() helper
    # (Settings > Technical > Logging), written on its own cursor so the
    # entries survive a rollback, plus the server log.
    # ------------------------------------------------------------------

    def _sss_log(self, message, level='info'):
        getattr(_logger, level if level in ('info', 'warning', 'error') else 'info')(
            "Créer tâches SSS: %s", message)
        try:
            with self.pool.cursor() as cr:
                cr.execute(
                    """INSERT INTO ir_logging(create_date, create_uid, type, dbname, name,
                                              level, message, path, line, func)
                       VALUES (NOW() at time zone 'UTC', %s, 'server', %s, %s, %s, %s, %s, %s, %s)""",
                    (self.env.uid, self.env.cr.dbname, __name__, level, message,
                     'action', '0', SSS_ACTION_NAME))
        except Exception:  # noqa: BLE001 - logging must never break the action
            _logger.exception("Créer tâches SSS: could not write ir.logging entry")

    def _sss_notify(self, title, message, ntype, sticky):
        self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
            'title': title,
            'message': message,
            'type': ntype,
            'sticky': sticky,
        })

    @api.model
    def _sss_filter_vals(self, model, vals):
        """Keep only the keys that are fields of `model` (the values below
        target field service modules; a missing one is logged, not fatal)."""
        fields_ = self.env[model]._fields
        unknown = [k for k in vals if k not in fields_]
        if unknown:
            self._sss_log(f"Fields not available on {model}, ignored: {', '.join(unknown)}",
                          level='warning')
        return {k: v for k, v in vals.items() if k in fields_}

    # ------------------------------------------------------------------
    # The action
    # ------------------------------------------------------------------

    def action_create_sss_tasks(self):
        """Create the SSS (field service) project, its stages and one task per
        consumable 'All / Saleable' line, for every selected order that is
        confirmed and has a paid or partially paid posted invoice."""
        env = self.env
        log = self._sss_log
        try:
            if not self:
                # Show info message if no records selected
                self._sss_notify('Aucun bon de commande',
                                 'Aucun bon de commande sélectionné.', 'warning', True)
                return

            sales_orders = self

            # Track statistics
            total_orders = len(sales_orders)
            projects_created = 0
            stages_created = 0
            total_tasks_created = 0
            orders_with_tasks = 0
            orders_skipped_no_payment = 0
            orders_skipped_not_confirmed = 0

            # Check current language context for stage names
            user_lang = env.user.lang or 'en_US'
            is_french = user_lang.startswith('fr')
            log(f"User language: {user_lang}, Using French names: {is_french}", level='info')

            # The one change versus the original action: the SSS project
            # manager comes from the system parameter (was left empty).
            sss_manager = env['project.project']._sss_project_manager()

            Project = env['project.project']
            project_has_fsm = 'is_fsm' in Project._fields

            # Process each sales order
            for record in sales_orders:
                # Check if this is a confirmed sales order
                if record.state == 'sale':
                    # ===== CHECK PAYMENT CONDITION =====
                    # Check if sales order has invoices with payment (complete or partial)
                    invoices = env['account.move'].search([
                        ('invoice_origin', '=', record.name),
                        ('move_type', '=', 'out_invoice'),
                        ('state', '=', 'posted')  # Only consider posted invoices
                    ])

                    has_payment = False
                    payment_info = []

                    for invoice in invoices:
                        # Check payment states: 'paid' (fully paid) or 'partial' (partially paid) or 'in_payment'
                        if invoice.payment_state in ['paid', 'partial', 'in_payment']:
                            has_payment = True
                            payment_info.append(f"{invoice.name} ({invoice.payment_state})")
                            log(f"Invoice {invoice.name} has payment status: {invoice.payment_state}", level='info')

                    if has_payment:
                        log(f"Sales order {record.name} has paid invoices: {', '.join(payment_info)}, proceeding with FSM creation", level='info')

                        # Proceed with FSM creation only if payment condition is met
                        log(f"Processing sales order: {record.name}", level='info')

                        # ===== ACTION 1: CREATE PROJECT AND STAGES =====

                        # Verify that a project doesn't already exist for this sales order
                        project_name = f"{record.name} - SSS - {record.partner_id.name}"
                        existing_domain = [('name', '=', project_name)]
                        if project_has_fsm:
                            existing_domain.append(('is_fsm', '=', True))
                        existing_project = Project.search(existing_domain, limit=1)

                        project = existing_project

                        if not existing_project:
                            # Create project with field service characteristics
                            project_vals = {
                                'name': project_name,
                                'partner_id': record.partner_id.id,
                                'company_id': record.company_id.id,
                                'sale_order_id': record.id,
                                # Project manager: fixed user from the system parameter
                                # (empty when the parameter is not set).
                                'user_id': sss_manager.id if sss_manager else False,

                                # Field service specific characteristics from example
                                'is_fsm': True,
                                'allow_timesheets': True,
                                'allow_material': False,  # Based on project example
                                'allow_worksheets': True,
                                'allow_billable': False,  # Based on project example
                                'allow_milestones': False,
                                'allow_quotations': False,
                                'allow_task_dependencies': True,
                                'privacy_visibility': 'employees',  # Based on project example
                                # 'use_documents': True,
                                'billing_type': 'not_billable',  # Based on project example
                                'worksheet_template_id': 1,  # Default Worksheet from example
                                'label_tasks': 'Tâches - Service sur Site',  # Based on example
                            }

                            project = Project.create(self._sss_filter_vals('project.project', project_vals))

                            # Link the project to the sales order
                            record.write({'project_ids': [(4, project.id)]})

                            log(f"Field Service Project created: {project.name} (ID: {project.id})", level='info')
                            projects_created += 1

                            # Create project stages
                            log(f"Creating project stages for: {project.name}", level='info')

                            # Define stages in both languages with FSM prefix to distinguish from admin stages
                            stages_data = [
                                {
                                    'name': 'FSM: ToDo',
                                    'name_fr': 'SSS: À faire',
                                    'sequence': 1,
                                    'fold': False,
                                    'active': True
                                },
                                {
                                    'name': 'FSM: In progress/Done',
                                    'name_fr': 'SSS: Encours/Fait',
                                    'sequence': 2,
                                    'fold': False,
                                    'active': True
                                }
                            ]

                            created_stages_for_project = []

                            for stage_data in stages_data:
                                # Use French name if user language is French, otherwise English
                                stage_name = stage_data['name_fr'] if is_french else stage_data['name']

                                # Check if stage already exists for this project
                                existing_stage = env['project.task.type'].search([
                                    ('name', '=', stage_name),
                                    ('project_ids', 'in', [project.id])
                                ], limit=1)

                                if not existing_stage:
                                    # Create the stage
                                    stage_vals = {
                                        'name': stage_name,
                                        'sequence': stage_data['sequence'],
                                        'fold': stage_data['fold'],
                                        'active': stage_data['active'],
                                        'project_ids': [(4, project.id)]  # Link to the project
                                    }

                                    stage = env['project.task.type'].create(stage_vals)
                                    created_stages_for_project.append(stage.name)
                                    stages_created += 1
                                    log(f"Created stage: {stage.name} (ID: {stage.id})", level='info')

                            if created_stages_for_project:
                                log(f"Successfully created {len(created_stages_for_project)} stages for project {project.name}: {', '.join(created_stages_for_project)}", level='info')
                            else:
                                log(f"All stages already existed for project {project.name}", level='info')
                        else:
                            log(f"Project already exists for sales order {record.name}: {existing_project.name}", level='info')

                        # ===== ACTION 2: CREATE TASKS =====

                        if project:
                            log(f"Creating tasks for project: {project.name} (ID: {project.id})", level='info')

                            # Get the initial task stage - look for "ToDo" or "À faire" stages
                            # Look for the "FSM: ToDo" stage created for this specific project
                            initial_stage_names = ['SSS: À faire'] if is_french else ['FSM: ToDo']

                            fsm_stage = env['project.task.type'].search([
                                ('name', 'in', initial_stage_names),
                                ('project_ids', 'in', [project.id])  # Make sure it's linked to this project
                            ], limit=1)

                            # If no project-specific stage found, look for any matching FSM stage
                            if not fsm_stage:
                                fsm_stage = env['project.task.type'].search([
                                    ('name', 'in', ['FSM: ToDo', 'SSS: À faire'])
                                ], limit=1)

                            # If still no matching stage found, get the first available stage for this project
                            if not fsm_stage:
                                fsm_stage = env['project.task.type'].search([
                                    ('project_ids', 'in', [project.id])
                                ], limit=1)

                            if fsm_stage:
                                log(f"Using stage: {fsm_stage.name} (ID: {fsm_stage.id}) for new tasks", level='info')
                            else:
                                log("Warning: No task stage found, tasks will be created without stage", level='warning')

                            created_tasks_for_order = []

                            # Iterate through each order line to create a task
                            for line in record.order_line:
                                # Only create tasks for products that are:
                                # 1. In "All / Saleable" category (including subcategories)
                                # 2. Consumable products (type == 'consu')
                                if (line.product_id and
                                        line.product_id.categ_id and
                                        line.product_id.categ_id.complete_name.startswith('All / Saleable') and
                                        line.product_id.type == 'consu'):

                                    # Check that a task doesn't already exist for this product in this project
                                    existing_task = env['project.task'].search([
                                        ('name', '=', line.product_id.name),
                                        ('project_id', '=', project.id),
                                        ('sale_order_id', '=', record.id)
                                    ], limit=1)

                                    if not existing_task:
                                        # Prepare task values with FSM characteristics - linked to sales order only
                                        task_vals = {
                                            'name': f"{line.product_id.name}",
                                            'project_id': project.id,
                                            'partner_id': record.partner_id.id,
                                            # Link to sales order but NOT to sale line
                                            'sale_order_id': record.id,
                                            'company_id': record.company_id.id,
                                            # Leave tasks unassigned at creation - will be assigned later during planning
                                            'user_ids': [(5,)],  # Clear any default assignments

                                            # Critical characteristics for field service (matching project settings)
                                            'is_fsm': True,
                                            'allow_timesheets': True,
                                            'allow_material': False,  # Match project setting
                                            'allow_worksheets': True,
                                            'allow_billable': False,  # Match project setting
                                            'allow_milestones': False,
                                            'allow_quotations': False,
                                            'allow_task_dependencies': False,

                                            # Hours and pricing configuration
                                            'allocated_hours': line.product_uom_qty if line.product_uom_qty > 0 else 1,
                                            'remaining_hours': line.product_uom_qty if line.product_uom_qty > 0 else 1,
                                            'pricing_type': 'task_rate',  # Based on FSM example

                                            # Stage and state - use the correct stage
                                            'stage_id': fsm_stage.id if fsm_stage else False,
                                            'state': '01_in_progress',

                                            # Default worksheet template
                                            'worksheet_template_id': 1,  # "Default Worksheet" based on example

                                            # Product for timesheets
                                            'timesheet_product_id': line.product_id.id,

                                            # Customer information (copied from FSM example)
                                            'partner_city': record.partner_id.city or '',
                                            'partner_country_id': record.partner_id.country_id.id if record.partner_id.country_id else False,
                                            'partner_phone': record.partner_id.phone or '',
                                            'partner_street': record.partner_id.street or '',
                                            'partner_street2': record.partner_id.street2 or '',
                                            'partner_zip': record.partner_id.zip or '',

                                            # Billing configuration
                                            'pricelist_id': record.pricelist_id.id if record.pricelist_id else False,
                                            'currency_id': record.currency_id.id,
                                        }

                                        # Create the task
                                        task = env['project.task'].create(self._sss_filter_vals('project.task', task_vals))
                                        created_tasks_for_order.append(task.name)
                                        total_tasks_created += 1

                                        log(f"Field Service Task created: {task.name} (ID: {task.id}) with stage: {fsm_stage.name if fsm_stage else 'No stage'} for line: {line.product_id.name}", level='info')

                            if created_tasks_for_order:
                                log(f"Successfully created {len(created_tasks_for_order)} tasks for order {record.name}: {', '.join(created_tasks_for_order)}", level='info')
                                orders_with_tasks += 1
                            else:
                                log(f"No tasks created for order {record.name} - all order lines may already have tasks or no valid products found", level='warning')
                        else:
                            log(f"No project available for sales order {record.name} - tasks cannot be created", level='error')
                    else:
                        log(f"Sales order {record.name} has no paid invoices, skipping FSM creation", level='warning')
                        orders_skipped_no_payment += 1
                else:
                    log(f"Sales order {record.name} is not confirmed (state: {record.state}), skipping", level='warning')
                    orders_skipped_not_confirmed += 1

            # Calculate valid orders (confirmed and paid)
            valid_orders = total_orders - orders_skipped_no_payment - orders_skipped_not_confirmed
            invalid_orders = orders_skipped_no_payment + orders_skipped_not_confirmed

            # Show appropriate message based on results
            if valid_orders == 0:
                # No valid orders - show warning
                self._sss_notify('Aucune commande valide',
                                 'Aucune commande client payée (complètement/partiellement) sélectionnées.',
                                 'warning', True)
            else:
                # Some valid orders processed - show success with detailed breakdown
                message_parts = []

                # Add valid/invalid breakdown
                if invalid_orders > 0:
                    message_parts.append(f'{valid_orders} commandes client valides payées (complètement/partiellement) / {invalid_orders} non valides')
                else:
                    message_parts.append(f'{valid_orders} commandes client valides payées (complètement/partiellement)')

                # Add creation results
                creation_parts = []
                if projects_created > 0:
                    creation_parts.append(f'{projects_created} projets SSS créés')
                if total_tasks_created > 0:
                    creation_parts.append(f'{total_tasks_created} tâches SSS créées')

                if creation_parts:
                    message_parts.append(' - '.join(creation_parts))
                else:
                    message_parts.append('Aucun élément créé (projets/tâches déjà existants)')

                final_message = ' | '.join(message_parts)

                self._sss_notify('Traitement FSM terminé', final_message, 'success', False)

            # Log final summary
            log(f"FSM Processing Complete - Valid orders: {valid_orders}/{total_orders}, Projects: {projects_created}, Stages: {stages_created}, Tasks: {total_tasks_created}, Skipped (no payment): {orders_skipped_no_payment}, Skipped (not confirmed): {orders_skipped_not_confirmed}", level='info')

        except Exception as e:  # noqa: BLE001 - same behaviour as the server action
            # Log the error and show an error message to the user
            log(f"Error in Combined FSM Creation action: {str(e)}", level='error')
            self._sss_notify('Erreur', f"Erreur lors de la création tâches SSS : {str(e)}",
                             'danger', True)
