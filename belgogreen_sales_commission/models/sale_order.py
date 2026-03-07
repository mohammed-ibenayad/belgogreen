# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
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
        _logger.info("=== COMMISSION V2 === action_generate_commissions called for order %s (ID: %s)", self.name, self.id)
        result = self._generate_commissions()

        # Show notification to user
        if result['success']:
            message_type = 'success'
            title = _('Commissions générées')
        else:
            message_type = 'warning'
            title = _('Génération de commissions')

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

    def _check_commission_eligibility(self):
        """
        Check if the sale order is eligible for commission calculation.

        Rules (from spec):
        1. All eligible invoices linked to the SO must be fully paid.
        2. The sum of eligible invoices must exactly match the SO total (to the cent).
        3. No active credit notes (avoirs) may exist for this SO.

        Eligible invoices: all invoices (out_invoice) linked to the SO,
        excluding cancelled invoices and credit notes (out_refund).

        Returns: dict with 'eligible', 'message', 'eligible_invoices', 'base_amount'
        """
        self.ensure_one()

        result = {
            'eligible': False,
            'message': '',
            'eligible_invoices': self.env['account.move'],
            'base_amount': 0.0,
        }

        # Eligible invoices = out_invoice, not cancelled
        all_invoices = self.invoice_ids
        _logger.info(
            "=== COMMISSION V2 === Eligibility check for order %s: "
            "SO total=%.2f, all linked invoices=%s",
            self.name, self.amount_total,
            [(inv.name, inv.move_type, inv.state, inv.payment_state, inv.amount_total)
             for inv in all_invoices]
        )

        eligible_invoices = all_invoices.filtered(
            lambda inv: inv.move_type == 'out_invoice' and inv.state != 'cancel'
        )

        _logger.info(
            "=== COMMISSION V2 === Eligible invoices (out_invoice, not cancelled): %s",
            [(inv.name, inv.amount_total, inv.payment_state) for inv in eligible_invoices]
        )

        if not eligible_invoices:
            result['message'] = _("Aucune facture éligible trouvée pour la commande %s") % self.name
            _logger.info("=== COMMISSION V2 === BLOCKED: no eligible invoices")
            return result

        # Block if any non-cancelled credit notes exist
        active_credit_notes = all_invoices.filtered(
            lambda inv: inv.move_type == 'out_refund' and inv.state != 'cancel'
        )

        if active_credit_notes:
            result['message'] = _(
                "La commande %s possède des notes de crédit actives - la commission ne peut pas être calculée"
            ) % self.name
            _logger.info(
                "=== COMMISSION V2 === BLOCKED: active credit notes found: %s",
                active_credit_notes.mapped('name')
            )
            return result

        # ALL eligible invoices must be fully paid
        unpaid_invoices = eligible_invoices.filtered(
            lambda inv: inv.payment_state != 'paid'
        )

        if unpaid_invoices:
            result['message'] = _(
                "La commande %s a des factures éligibles non payées : %s"
            ) % (self.name, ', '.join(unpaid_invoices.mapped('name')))
            _logger.info(
                "=== COMMISSION V2 === BLOCKED: unpaid invoices: %s",
                [(inv.name, inv.payment_state) for inv in unpaid_invoices]
            )
            return result

        # Sum of eligible invoices must exactly match SO total (no rounding tolerance)
        eligible_total = sum(eligible_invoices.mapped('amount_total'))
        precision = self.currency_id.decimal_places

        _logger.info(
            "=== COMMISSION V2 === Amount check: eligible_total=%.2f, so_total=%.2f, precision=%d, match=%s",
            eligible_total, self.amount_total, precision,
            float_compare(eligible_total, self.amount_total, precision_digits=precision) == 0
        )

        if float_compare(eligible_total, self.amount_total, precision_digits=precision) != 0:
            result['message'] = _(
                "Commande %(order)s : le total des factures éligibles (%(inv_total).2f) ne correspond pas "
                "au total de la commande (%(so_total).2f)"
            ) % {
                'order': self.name,
                'inv_total': eligible_total,
                'so_total': self.amount_total,
            }
            _logger.info("=== COMMISSION V2 === BLOCKED: amount mismatch")
            return result

        # All checks passed
        result['eligible'] = True
        result['eligible_invoices'] = eligible_invoices
        result['base_amount'] = eligible_total

        _logger.info("=== COMMISSION V2 === ELIGIBLE: all checks passed, base_amount=%.2f", eligible_total)
        return result

    def _generate_commissions(self):
        """
        Generate commissions for this sale order if conditions are met.

        Commission is only created when:
        - The SO is fully invoiced (sum of eligible invoices = SO total)
        - All eligible invoices are fully paid
        - No active credit notes exist

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
            result['message'] = _("La commande %s n'est pas confirmée (état : %s)") % (self.name, self.state)
            return result

        # Check if salesperson is assigned
        if not self.user_id:
            result['message'] = _("Aucun vendeur assigné à la commande %s") % self.name
            return result

        # Find ALL applicable commission plans
        commission_plans = self.env['sale.commission.plan'].search([
            ('type', '=', 'hierarchical'),
            ('state', '=', 'approved'),
            ('company_id', '=', self.company_id.id)
        ])

        if not commission_plans:
            result['message'] = _("Aucun plan de commission hiérarchique approuvé trouvé")
            return result

        # Check commission eligibility (new spec rules)
        eligibility = self._check_commission_eligibility()

        if not eligibility['eligible']:
            result['message'] = eligibility['message']
            return result

        base_amount = eligibility['base_amount']
        eligible_invoices = eligibility['eligible_invoices']

        # Use the most recent eligible invoice date for date validation
        invoice_date = fields.Date.today()
        if eligible_invoices:
            dates = [d for d in eligible_invoices.mapped('invoice_date') if d]
            if dates:
                invoice_date = max(dates)

        # Process each commission plan
        total_commissions_created = 0
        plans_processed = []

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

            # Create commissions for the entire order (not per invoice)
            commissions_created = self._create_commissions_for_order(
                base_amount, eligible_invoices, commission_plan
            )

            if commissions_created > 0:
                total_commissions_created += commissions_created
                plans_processed.append(commission_plan.name)
                _logger.info("Created %s commission(s) for plan %s on order %s",
                           commissions_created, commission_plan.name, self.name)

        if total_commissions_created > 0:
            self.commissions_generated = True
            result['success'] = True
            result['message'] = _("%s commission(s) créée(s) sur %s plan(s) (%s) pour la commande %s") % (
                total_commissions_created, len(plans_processed), ', '.join(plans_processed), self.name
            )
            result['commissions_created'] = total_commissions_created
        else:
            result['message'] = _("Aucune nouvelle commission à générer - vos données sont à jour")

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
                lambda inv: inv.move_type == 'out_invoice' and inv.payment_state == 'paid'
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

    def _create_commissions_for_order(self, base_amount, eligible_invoices, commission_plan):
        """
        Create commission records for the entire sale order.

        Commission base = sum of all eligible invoices (which must equal SO total).
        One commission per user in the hierarchy, not per invoice.

        LEGACY SUPPORT: If ANY legacy commission flag is true on the sale order,
        commission generation is completely blocked for that order.

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

        # Build commission hierarchy dynamically
        users_to_commission = self._get_commission_hierarchy(salesperson, commission_plan)

        if not users_to_commission:
            _logger.info("No commission hierarchy found for user %s in plan %s", salesperson.name, commission_plan.name)
            return 0

        # Use the most recent eligible invoice date for period
        invoice_date = fields.Date.today()
        if eligible_invoices:
            dates = [d for d in eligible_invoices.mapped('invoice_date') if d]
            if dates:
                invoice_date = max(dates)

        period = invoice_date.strftime('%Y-%m')

        # Create commission records
        commissions_created = 0
        for user, role, commission_type in users_to_commission:
            # Check if commission already exists for this SO + plan + user + role
            existing_commission = self.env['sale.commission'].search([
                ('sale_order_id', '=', self.id),
                ('plan_id', '=', commission_plan.id),
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

            # Create commission record - base_amount covers entire SO
            try:
                self.env['sale.commission'].sudo().create({
                    'user_id': user.id,
                    'role_id': role.id,
                    'commission_type': commission_type,
                    'sale_order_id': self.id,
                    'invoice_id': False,  # Commission covers entire SO, not a single invoice
                    'plan_id': commission_plan.id,
                    'date': invoice_date,
                    'period': period,
                    'base_amount': base_amount,
                    'status': 'unpaid',
                    'company_id': self.company_id.id,
                    'currency_id': self.currency_id.id,
                })
                commissions_created += 1
                _logger.info("Created commission for %s (%s, %s) - Order: %s, Base: %.2f",
                           user.name, role.name, commission_type, self.name, base_amount)
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

    def action_generate_commissions_bulk(self):
        """
        Bulk action to generate commissions for multiple selected sale orders
        Can be called from sale order list view
        Returns detailed feedback about processed orders
        """
        # Check if user has commission manager rights
        if not self.env.user.has_group('belgogreen_sales_commission.group_commission_manager'):
            raise UserError(_('Only Commission Managers can generate commissions.'))

        if not self:
            raise UserError(_('Please select at least one sale order.'))

        # Track results
        total_commissions_created = 0
        orders_processed = []
        orders_skipped = []
        orders_with_errors = []

        for order in self:
            try:
                result = order._generate_commissions()

                if result['success']:
                    orders_processed.append({
                        'name': order.name,
                        'commissions': result['commissions_created']
                    })
                    total_commissions_created += result['commissions_created']
                else:
                    orders_skipped.append({
                        'name': order.name,
                        'reason': result['message']
                    })

            except Exception as e:
                orders_with_errors.append({
                    'name': order.name,
                    'error': str(e)
                })
                _logger.error("Error generating commissions for order %s: %s", order.name, str(e))

        # Build simple feedback message
        message_parts = []

        # Main summary line
        if total_commissions_created > 0:
            message_parts.append(_('%s commission(s) created successfully!') % total_commissions_created)
        else:
            message_parts.append(_('No new commissions created.'))

        # Brief stats
        message_parts.append(_('\nOrders selected: %s') % len(self))
        message_parts.append(_('Orders processed: %s') % len(orders_processed))

        if orders_skipped:
            message_parts.append(_('Orders skipped: %s') % len(orders_skipped))

        if orders_with_errors:
            message_parts.append(_('Orders with errors: %s') % len(orders_with_errors))

        message = '\n'.join(message_parts)

        # Determine notification type
        if orders_with_errors:
            message_type = 'warning'
            title = _('Commission Generation - With Errors')
        elif total_commissions_created > 0:
            message_type = 'success'
            title = _('Commission Generation - Success')
        else:
            message_type = 'info'
            title = _('Commission Generation - No New Commissions')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': message_type,
                'sticky': False,
            }
        }

    @api.model
    def cron_generate_commissions(self):
        """
        Scheduled action to generate commissions for all eligible sale orders.
        Runs nightly to process any orders that meet full invoicing + payment criteria.
        """
        _logger.info("Starting scheduled commission generation...")

        # Find confirmed sale orders with a salesperson
        orders = self.search([
            ('state', 'in', ['sale', 'done']),
            ('user_id', '!=', False),
        ])

        total_orders_processed = 0
        total_commissions_created = 0
        errors = []

        for order in orders:
            try:
                # _generate_commissions handles all eligibility checks internally
                result = order._generate_commissions()
                if result['success']:
                    total_orders_processed += 1
                    total_commissions_created += result['commissions_created']
                    _logger.info("Processed order %s: %s", order.name, result['message'])

            except Exception as e:
                error_msg = _("Error processing order %s: %s") % (order.name, str(e))
                _logger.error(error_msg)
                errors.append(error_msg)

        _logger.info(
            "Scheduled commission generation completed. Processed %s orders, created %s commissions.",
            total_orders_processed, total_commissions_created
        )

        if errors:
            _logger.warning("Encountered %s errors during commission generation", len(errors))

        return {
            'orders_processed': total_orders_processed,
            'commissions_created': total_commissions_created,
            'errors': errors
        }
