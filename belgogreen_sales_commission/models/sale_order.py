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
        groups='belgogreen_sales_commission.group_commission_user',
        help='Commissions generated from this sale order'
    )

    commission_count = fields.Integer(
        string='Commission Count',
        compute='_compute_commission_count',
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
            order.commission_count = len(order.sudo().commission_ids)

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
        1. All eligible invoices AND active credit notes must be fully paid.
        2. The sum of eligible invoices must be at least the SO total (to the cent).
        3. Active credit notes (avoirs) do not block: their untaxed amount is
           deducted from the commission base. The order is ineligible only if the
           credit notes cancel out the invoiced amount (net base <= 0).

        Eligible invoices: all invoices (out_invoice) linked to the SO,
        excluding cancelled invoices. Credit notes (out_refund, not cancelled)
        are handled separately: they must be paid and reduce the base.

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

        # Active credit notes (avoirs) for this SO = out_refund, not cancelled.
        # These are no longer a hard block: instead they must be fully paid (just
        # like invoices) and their untaxed amount is deducted from the commission
        # base further down.
        credit_notes = all_invoices.filtered(
            lambda inv: inv.move_type == 'out_refund' and inv.state != 'cancel'
        )

        # ALL eligible invoices AND credit notes must be fully paid.
        # An unpaid invoice OR an unpaid credit note blocks generation.
        unpaid_documents = (eligible_invoices | credit_notes).filtered(
            lambda inv: inv.payment_state != 'paid'
        )

        if unpaid_documents:
            result['message'] = _(
                "La commande %s a des factures ou notes de crédit non payées : %s"
            ) % (self.name, ', '.join(unpaid_documents.mapped('name')))
            _logger.info(
                "=== COMMISSION V2 === BLOCKED: unpaid invoices/credit notes: %s",
                [(inv.name, inv.move_type, inv.payment_state) for inv in unpaid_documents]
            )
            return result

        # Sum of eligible invoices must be at least equal to SO total
        # (client may pay more than SO total, which is allowed)
        eligible_total = sum(eligible_invoices.mapped('amount_total'))
        precision = self.currency_id.decimal_places

        _logger.info(
            "=== COMMISSION V2 === Amount check: eligible_total=%.2f, so_total=%.2f, precision=%d, gte=%s",
            eligible_total, self.amount_total, precision,
            float_compare(eligible_total, self.amount_total, precision_digits=precision) >= 0
        )

        if float_compare(eligible_total, self.amount_total, precision_digits=precision) < 0:
            result['message'] = _(
                "Commande %(order)s : le total des factures éligibles (%(inv_total).2f) est inférieur "
                "au total de la commande (%(so_total).2f)"
            ) % {
                'order': self.name,
                'inv_total': eligible_total,
                'so_total': self.amount_total,
            }
            _logger.info("=== COMMISSION V2 === BLOCKED: invoice total less than SO total")
            return result

        # All checks passed. The eligibility gate above compares TTC totals (the
        # client must have paid at least the SO total), but the commission itself
        # is calculated on the untaxed (HTVA) amount, never on the VAT.
        #
        # Paid credit notes (avoirs) reduce the commission base: their untaxed
        # amount is deducted from the invoices' untaxed amount.
        invoice_untaxed = sum(eligible_invoices.mapped('amount_untaxed'))
        credit_note_untaxed = sum(credit_notes.mapped('amount_untaxed'))
        base_amount = invoice_untaxed - credit_note_untaxed

        # If credit notes cancel out (or exceed) the invoiced amount, there is no
        # positive base left, so no commission is generated.
        if float_compare(base_amount, 0.0, precision_digits=precision) <= 0:
            result['message'] = _(
                "Commande %(order)s : les notes de crédit (%(cn).2f HTVA) annulent la base "
                "de commission (factures %(inv).2f HTVA)"
            ) % {
                'order': self.name,
                'cn': credit_note_untaxed,
                'inv': invoice_untaxed,
            }
            _logger.info(
                "=== COMMISSION V2 === BLOCKED: credit notes cancel commission base "
                "(invoice_untaxed=%.2f, credit_note_untaxed=%.2f)",
                invoice_untaxed, credit_note_untaxed
            )
            return result

        result['eligible'] = True
        result['eligible_invoices'] = eligible_invoices
        result['base_amount'] = base_amount

        _logger.info(
            "=== COMMISSION V2 === ELIGIBLE: base_amount (HTVA, net of credit notes)=%.2f "
            "(invoices=%.2f, credit notes=%.2f)",
            base_amount, invoice_untaxed, credit_note_untaxed
        )
        return result

    def _generate_commissions(self):
        """
        Generate commissions for this sale order if conditions are met.

        Commission is only created when:
        - The SO is fully invoiced (sum of eligible invoices = SO total)
        - All eligible invoices AND active credit notes are fully paid
        - Active credit notes are deducted from the base (net base > 0)

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
            # Check if salesperson has an assignment active on the invoice date
            # (line dates first, plan effective period as fallback)
            user_assignment = self._get_active_plan_assignment(
                commission_plan, self.user_id, invoice_date)

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

    def _get_active_plan_assignment(self, commission_plan, user, check_date):
        """Return the user's assignment in this plan if it is active on check_date.

        The assignment line's own date_from/date_to take precedence. When a
        line date is not set, the plan's effective period (date_from/date_to)
        applies as fallback, so a plan bounded to one year can never generate
        outside that year just because a line date was left empty.

        Returns an empty recordset when the user has no assignment or the
        assignment is not valid on check_date.
        """
        PlanUser = self.env['sale.commission.plan.user']
        plan_user = PlanUser.search([
            ('plan_id', '=', commission_plan.id),
            ('user_id', '=', user.id),
        ], limit=1)
        if not plan_user:
            return PlanUser
        date_from = plan_user.date_from or commission_plan.date_from
        date_to = plan_user.date_to or commission_plan.date_to
        if date_from and check_date < date_from:
            return PlanUser
        if date_to and check_date > date_to:
            return PlanUser
        return plan_user

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
            # Find user's assignment in THIS PLAN, active on the invoice date
            # (line dates first, plan effective period as fallback)
            plan_user = self._get_active_plan_assignment(
                commission_plan, current_user, invoice_date)

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
            # Anti-duplicate guard: one commission per beneficiary + order +
            # type, whatever the plan or role it came from (manual commissions
            # included). Cancelled records do not block regeneration.
            existing_commission = self.env['sale.commission'].sudo().search([
                ('sale_order_id', '=', self.id),
                ('user_id', '=', user.id),
                ('commission_type', '=', commission_type),
                ('status', '!=', 'cancelled'),
            ], limit=1)

            if existing_commission:
                _logger.info(
                    "Commission %s already exists for %s (%s) on order %s - "
                    "skipping duplicate from plan %s",
                    existing_commission.name, user.name, commission_type,
                    self.name, commission_plan.name)
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

            # Skip if the commission percentage is 0%
            applicable_percentage = (
                role_config.direct_sale_percentage if commission_type == 'direct'
                else role_config.override_percentage
            )
            if not applicable_percentage:
                _logger.info(
                    "Skipping commission for %s (%s, %s) - percentage is 0%%",
                    user.name, role.name, commission_type
                )
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
