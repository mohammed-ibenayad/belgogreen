# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    commission_ids = fields.One2many(
        'sale.commission',
        'sale_order_id',
        string='Commissions',
        help='Commissions generated from this sale order'
    )

    commission_count = fields.Integer(
        string='Commission Count',
        compute='_compute_commission_count'
    )

    commissions_generated = fields.Boolean(
        string='Commissions Generated',
        default=False,
        help='Indicates if commissions have been generated for this order'
    )

    @api.depends('commission_ids')
    def _compute_commission_count(self):
        """Count commissions for this sale order"""
        for order in self:
            order.commission_count = len(order.commission_ids)

    def action_generate_commissions(self):
        """
        Manual action to generate commissions for this sale order
        Can be called from a button or scheduled action
        """
        self.ensure_one()
        result = self._generate_commissions()

        # Show notification to user
        if result['success']:
            message_type = 'success'
            title = _('Commissions Generated')
        else:
            message_type = 'warning'
            title = _('Commission Generation')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': result['message'],
                'type': message_type,
                'sticky': False,
            }
        }

    def _generate_commissions(self):
        """
        Generate commissions for this sale order if conditions are met
        Returns: dict with result information
        """
        self.ensure_one()

        result = {
            'success': False,
            'message': '',
            'commissions_created': 0
        }

        # Check if order is confirmed
        if self.state not in ['sale', 'done']:
            result['message'] = _("Order %s is not confirmed (state: %s)") % (self.name, self.state)
            return result

        # Check if salesperson is assigned
        if not self.user_id:
            result['message'] = _("No salesperson assigned to order %s") % self.name
            return result

        # Find ALL applicable commission plans (removed limit=1)
        commission_plans = self.env['sale.commission.plan'].search([
            ('type', '=', 'hierarchical'),
            ('state', '=', 'approved'),
            ('company_id', '=', self.company_id.id)
        ])

        if not commission_plans:
            result['message'] = _("No approved hierarchical commission plan found")
            return result

        # Get paid invoices for this sale order
        paid_invoices = self.invoice_ids.filtered(
            lambda inv: inv.move_type == 'out_invoice'
            and inv.state == 'posted'
            and inv.payment_state in ['paid', 'in_payment']
        )

        if not paid_invoices:
            result['message'] = _("No paid invoices found for order %s") % self.name
            return result

        # Process each commission plan
        total_commissions_created = 0
        plans_processed = []
        invoice_date = fields.Date.today()  # Use today for initial check

        for commission_plan in commission_plans:
            # Check if salesperson has assignment in this plan (with date validation)
            user_assignment = self.env['sale.commission.plan.user'].search([
                ('plan_id', '=', commission_plan.id),
                ('user_id', '=', self.user_id.id),
                # Date validation: assignment must be active
                '|', ('date_from', '=', False), ('date_from', '<=', invoice_date),
                '|', ('date_to', '=', False), ('date_to', '>=', invoice_date)
            ], limit=1)

            if not user_assignment:
                _logger.info("Salesperson %s is not assigned to commission plan %s, skipping",
                           self.user_id.name, commission_plan.name)
                continue

            # Check if plan requires paid invoice
            if commission_plan.require_invoice_paid and not paid_invoices:
                _logger.info("Commission plan %s requires paid invoices, but none found for order %s, skipping",
                           commission_plan.name, self.name)
                continue

            # Process each paid invoice for this plan
            commissions_created = 0
            for invoice in paid_invoices:
                created = self._create_commissions_for_invoice(invoice, commission_plan)
                commissions_created += created

            if commissions_created > 0:
                total_commissions_created += commissions_created
                plans_processed.append(commission_plan.name)
                _logger.info("Created %s commission(s) for plan %s on order %s",
                           commissions_created, commission_plan.name, self.name)

        if total_commissions_created > 0:
            self.commissions_generated = True
            result['success'] = True
            result['message'] = _("Successfully created %s commission(s) across %s plan(s) (%s) for order %s") % (
                total_commissions_created, len(plans_processed), ', '.join(plans_processed), self.name
            )
            result['commissions_created'] = total_commissions_created
        else:
            result['message'] = _("No new commissions to generate - your data is up to date")

        return result

    def _get_commission_hierarchy(self, base_user, commission_plan):
        """
        Traverse hierarchy upwards from base user to collect all managers who should receive commission.

        NOW USES PLAN-SPECIFIC ROLES: Each user's role and manager are determined by their
        assignment in the specific commission plan, not from global res.users fields.

        Supports unlimited hierarchy levels by following manager_id chain in plan assignments.
        Includes cycle detection to prevent infinite loops.

        NEW: Validates date_from and date_to to ensure user assignment is active on invoice date.

        Args:
            base_user: res.users record (typically the salesperson who made the sale)
            commission_plan: sale.commission.plan record (the plan to use for hierarchy)

        Returns:
            list of tuples: [(user, role, commission_type), ...] ordered from bottom to top of hierarchy
        """
        hierarchy = []
        current_user = base_user
        seen_ids = set()  # Cycle detection
        # Use invoice date from the first paid invoice for this order
        invoice_date = fields.Date.today()
        if self.invoice_ids:
            paid_invoice = self.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice' and inv.payment_state in ['paid', 'in_payment']
            )[:1]
            if paid_invoice and paid_invoice.invoice_date:
                invoice_date = paid_invoice.invoice_date

        while current_user and current_user.id not in seen_ids:
            # Find user's assignment in THIS PLAN (with date validation)
            plan_user = self.env['sale.commission.plan.user'].search([
                ('plan_id', '=', commission_plan.id),
                ('user_id', '=', current_user.id),
                # Date validation: assignment must be active on invoice date
                '|', ('date_from', '=', False), ('date_from', '<=', invoice_date),
                '|', ('date_to', '=', False), ('date_to', '>=', invoice_date)
            ], limit=1)

            if plan_user and plan_user.role_id:
                # Determine commission type
                is_direct_sale = (current_user.id == base_user.id)  # First person in chain = made the sale
                commission_type = 'direct' if is_direct_sale else 'override'

                # Use PLAN-SPECIFIC role
                hierarchy.append((current_user, plan_user.role_id, commission_type))
                seen_ids.add(current_user.id)

                # Move up to manager IN THIS PLAN
                current_user = plan_user.manager_id
            else:
                # User not in this plan, stop traversal
                break

            # Safety check: prevent infinite loops
            if len(seen_ids) > 20:
                _logger.warning("Hierarchy depth exceeds 20 levels for user %s. Possible circular reference.", base_user.name)
                break

        return hierarchy

    def _create_commissions_for_invoice(self, invoice, commission_plan):
        """
        Create commission records for a specific invoice.
        Now supports dynamic N-level hierarchies with dual percentage (direct vs override).

        LEGACY SUPPORT: If ANY legacy commission flag is true on the sale order,
        commission generation is completely blocked for that order:
        - x_studio_payee_commercial
        - x_studio_payee_responsable_commercial
        - x_studio_payee_directeur_commercial

        Returns: number of commissions created
        """
        self.ensure_one()

        # LEGACY CHECK: Block commission generation if ANY legacy flag is true
        if (self.x_studio_payee_commercial or
            self.x_studio_payee_directeur_commercial or
            self.x_studio_payee_responsable_commercial):
            _logger.info("Legacy commission flags detected on order %s - commission generation blocked", self.name)
            return 0

        salesperson = self.user_id
        base_amount = invoice.amount_total

        # Build commission hierarchy dynamically - SUPPORTS ANY NUMBER OF LEVELS
        # NOW USES PLAN-SPECIFIC ROLES AND HIERARCHY
        users_to_commission = self._get_commission_hierarchy(salesperson, commission_plan)

        if not users_to_commission:
            _logger.info("No commission hierarchy found for user %s in plan %s", salesperson.name, commission_plan.name)
            return 0

        # Calculate period (YYYY-MM format)
        period = invoice.invoice_date.strftime('%Y-%m') if invoice.invoice_date else fields.Date.today().strftime('%Y-%m')

        # Create commission records
        commissions_created = 0
        for user, role, commission_type in users_to_commission:
            # User is already validated by hierarchy traversal (must be in plan)

            # Check if commission already exists for this specific user
            existing_commission = self.env['sale.commission'].search([
                ('invoice_id', '=', invoice.id),
                ('sale_order_id', '=', self.id),
                ('user_id', '=', user.id),
                ('role_id', '=', role.id),
                ('commission_type', '=', commission_type)
            ], limit=1)

            if existing_commission:
                _logger.info("Commission already exists for %s (%s, %s) on order %s",
                           user.name, role.name, commission_type, self.name)
                continue

            # Get role configuration
            role_config = self.env['hr.commission.role.config'].search([
                ('plan_id', '=', commission_plan.id),
                ('role_id', '=', role.id),
                ('active', '=', True)
            ], limit=1)

            if not role_config:
                _logger.warning("No active role config found for %s in plan %s", role.name, commission_plan.name)
                continue

            # Create commission record with role_id and commission_type
            # Use sudo() because this creates commissions for entire hierarchy (including managers)
            try:
                self.env['sale.commission'].sudo().create({
                    'user_id': user.id,
                    'role_id': role.id,
                    'commission_type': commission_type,  # NEW: direct or override
                    'sale_order_id': self.id,
                    'invoice_id': invoice.id,
                    'plan_id': commission_plan.id,
                    'date': invoice.invoice_date or fields.Date.today(),
                    'period': period,
                    'base_amount': base_amount,
                    'status': 'unpaid',
                    'company_id': self.company_id.id,
                    'currency_id': self.currency_id.id,
                })
                commissions_created += 1
                _logger.info("Created commission for %s (%s, %s) - Order: %s, Invoice: %s",
                           user.name, role.name, commission_type, self.name, invoice.name)
            except Exception as e:
                _logger.error("Error creating commission for %s: %s", user.name, str(e))

        return commissions_created

    def action_view_commissions(self):
        """View commissions for this sale order"""
        self.ensure_one()
        return {
            'name': _('Commissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.commission',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id}
        }

    @api.model
    def cron_generate_commissions(self):
        """
        Scheduled action to generate commissions for all eligible sale orders
        Runs nightly to process any orders with paid invoices
        """
        _logger.info("Starting scheduled commission generation...")

        # Find confirmed sale orders with paid invoices that haven't had commissions generated
        orders = self.search([
            ('state', 'in', ['sale', 'done']),
            ('user_id', '!=', False),
        ])

        total_orders_processed = 0
        total_commissions_created = 0
        errors = []

        for order in orders:
            try:
                # Check if order has paid invoices
                has_paid_invoices = order.invoice_ids.filtered(
                    lambda inv: inv.move_type == 'out_invoice'
                    and inv.state == 'posted'
                    and inv.payment_state in ['paid', 'in_payment']
                )

                if has_paid_invoices:
                    result = order._generate_commissions()
                    if result['success']:
                        total_orders_processed += 1
                        total_commissions_created += result['commissions_created']
                        _logger.info(_("Processed order %s: %s") % (order.name, result['message']))
                    elif result['message'] and 'already exist' not in result['message']:
                        # Only log if it's not about existing commissions
                        _logger.debug(_("Skipped order %s: %s") % (order.name, result['message']))

            except Exception as e:
                error_msg = _("Error processing order %s: %s") % (order.name, str(e))
                _logger.error(error_msg)
                errors.append(error_msg)

        _logger.info(
            _("Scheduled commission generation completed. Processed %s orders, created %s commissions.") % (total_orders_processed, total_commissions_created)
        )

        if errors:
            _logger.warning(_("Encountered %s errors during commission generation") % len(errors))

        return {
            'orders_processed': total_orders_processed,
            'commissions_created': total_commissions_created,
            'errors': errors
        }
