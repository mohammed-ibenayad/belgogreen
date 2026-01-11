# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    commission_ids = fields.One2many(
        'sale.commission',
        'invoice_id',
        string='Commissions',
        help='Commissions generated from this invoice'
    )

    commission_count = fields.Integer(
        string='Commission Count',
        compute='_compute_commission_count'
    )

    @api.depends('commission_ids')
    def _compute_commission_count(self):
        """Count commissions for this invoice"""
        for move in self:
            move.commission_count = len(move.commission_ids)

    def _create_hierarchical_commissions(self):
        """
        Create commissions for salesperson, team leader, and sales director
        when invoice is paid
        """
        self.ensure_one()

        # Only process customer invoices
        if self.move_type != 'out_invoice':
            return

        # Only process if invoice is paid (or in payment)
        if self.payment_state not in ['paid', 'in_payment']:
            return

        # Get the sale order(s) linked to this invoice
        sale_orders = self.invoice_line_ids.mapped('sale_line_ids.order_id')

        if not sale_orders:
            return

        # Process each sale order
        for sale_order in sale_orders:
            self._create_commission_for_sale(sale_order)

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
        invoice_date = self.invoice_date or fields.Date.today()

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
                break

        return hierarchy

    def _create_commission_for_sale(self, sale_order):
        """
        Create commissions for a specific sale order.
        Now supports dynamic N-level hierarchies with dual percentage (direct vs override).
        """
        # Get the salesperson
        salesperson = sale_order.user_id
        if not salesperson:
            return

        # Find applicable commission plan
        commission_plan = self.env['sale.commission.plan'].search([
            ('is_hierarchical', '=', True),
            ('state', '=', 'approved'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not commission_plan:
            return

        # Check if plan requires paid invoice
        if commission_plan.require_invoice_paid and self.payment_state not in ['paid', 'in_payment']:
            return

        # Calculate base amount for commissions
        base_amount = self.amount_total

        # Build commission hierarchy dynamically - SUPPORTS ANY NUMBER OF LEVELS
        # NOW USES PLAN-SPECIFIC ROLES AND HIERARCHY
        users_to_commission = self._get_commission_hierarchy(salesperson, commission_plan)

        if not users_to_commission:
            return

        # Calculate period (YYYY-MM format)
        period = self.invoice_date.strftime('%Y-%m') if self.invoice_date else fields.Date.today().strftime('%Y-%m')

        # Create commission records for each user in the hierarchy
        for user, role, commission_type in users_to_commission:
            # User is already validated by hierarchy traversal (must be in plan)

            # Check if commission already exists for this specific user
            existing_commission = self.env['sale.commission'].search([
                ('invoice_id', '=', self.id),
                ('sale_order_id', '=', sale_order.id),
                ('user_id', '=', user.id),
                ('role_id', '=', role.id),
                ('commission_type', '=', commission_type)
            ], limit=1)

            if existing_commission:
                continue

            # Check if there's a role configuration
            role_config = self.env['hr.commission.role.config'].search([
                ('plan_id', '=', commission_plan.id),
                ('role_id', '=', role.id),
                ('active', '=', True)
            ], limit=1)

            if not role_config:
                continue

            # Create commission record with role_id and commission_type
            self.env['sale.commission'].create({
                'user_id': user.id,
                'role_id': role.id,
                'commission_type': commission_type,  # NEW: direct or override
                'sale_order_id': sale_order.id,
                'invoice_id': self.id,
                'plan_id': commission_plan.id,
                'date': self.invoice_date or fields.Date.today(),
                'period': period,
                'base_amount': base_amount,
                'status': 'unpaid',
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
            })

    def write(self, vals):
        """Override write to trigger commission creation on payment and mark commissions paid"""
        # Store previous payment states before write
        previous_states = {}
        if 'line_ids' in vals or 'payment_state' in vals:
            for move in self:
                previous_states[move.id] = move.payment_state

        result = super(AccountMove, self).write(vals)

        for move in self:
            # Check if payment_state changed to paid (either directly or via reconciliation)
            payment_state_changed = (
                ('payment_state' in vals and move.payment_state in ['paid', 'in_payment']) or
                (move.id in previous_states and
                 previous_states[move.id] not in ['paid', 'in_payment'] and
                 move.payment_state in ['paid', 'in_payment'])
            )

            if payment_state_changed:
                # Create commissions for customer invoices
                if move.move_type == 'out_invoice':
                    move._create_hierarchical_commissions()

                # Mark commissions paid for vendor bills
                elif move.move_type == 'in_invoice':
                    move._mark_commissions_paid()

        return result

    def _mark_commissions_paid(self):
        """Mark commissions as paid when vendor bill is paid"""
        self.ensure_one()

        if not self.invoice_origin:
            return

        # Find the PO
        po = self.env['purchase.order'].search([
            ('name', '=', self.invoice_origin)
        ], limit=1)

        if not po:
            return  # Not a commission payment

        # Check if this is a commission PO (either claim-based or direct)
        if not po.claim_ids and not po.commission_ids:
            return  # Not a commission payment

        # Validate bill amount matches PO (within tolerance)
        if abs(self.amount_total - po.amount_total) > 1.0:
            # Log warning but don't block
            self.message_post(
                body=_(
                    'Warning: Bill amount (%(bill)s) does not match PO amount (%(po)s).\n'
                    'Difference: %(diff)s'
                ) % {
                    'bill': self.amount_total,
                    'po': po.amount_total,
                    'diff': abs(self.amount_total - po.amount_total),
                },
                subject=_('Amount Mismatch Warning'),
                message_type='notification'
            )

        # Find the account.payment that paid this bill
        # Get the payable line (the line that gets reconciled when bill is paid)
        payable_line = self.line_ids.filtered(
            lambda line: line.account_id.account_type in ('liability_payable', 'asset_receivable')
        )

        # Get payments from reconciled lines
        payments = self.env['account.payment']
        if payable_line:
            # Get all matched debits/credits (reconciliation records)
            matched_lines = payable_line.mapped('matched_debit_ids.debit_move_id') | \
                           payable_line.mapped('matched_credit_ids.credit_move_id')

            # Get payment records from those move lines
            payment_moves = matched_lines.mapped('move_id')
            payments = self.env['account.payment'].search([
                ('move_id', 'in', payment_moves.ids)
            ])

        # Get commissions (either from claims or direct)
        commissions = self.env['sale.commission']
        if po.claim_ids:
            # Claim-based commissions
            commissions = po.claim_ids.mapped('commission_ids')
            payment_type = 'claim-based'
            reference = ', '.join(po.claim_ids.mapped('name'))
        elif po.commission_ids:
            # Direct commissions (manager-initiated)
            commissions = po.commission_ids
            payment_type = 'direct'
            reference = ', '.join(commissions.mapped('name'))

        # Update commissions to paid
        commissions.write({
            'status': 'paid',
            'payment_date': self.invoice_date or fields.Date.today(),
            'payment_id': payments[0].id if payments else False,  # Link to first payment
        })

        # Log success
        if payment_type == 'claim-based':
            self.message_post(
                body=_(
                    'Commission payment completed!\n\n'
                    'Commissions paid: %(count)s\n'
                    'Total amount: %(amount)s\n'
                    'Payment: %(payment)s\n'
                    'Claims: %(claims)s'
                ) % {
                    'count': len(commissions),
                    'amount': self.amount_total,
                    'payment': payments[0].name if payments else 'N/A',
                    'claims': reference,
                },
                subject=_('Commissions Paid'),
            )
        else:  # direct
            self.message_post(
                body=_(
                    'Direct commission payment completed!\n\n'
                    'Commissions paid: %(count)s\n'
                    'Total amount: %(amount)s\n'
                    'Payment: %(payment)s\n'
                    'Commissions: %(commissions)s\n\n'
                    'Note: This was a direct payment initiated by a manager (no claim).'
                ) % {
                    'count': len(commissions),
                    'amount': self.amount_total,
                    'payment': payments[0].name if payments else 'N/A',
                    'commissions': reference,
                },
                subject=_('Direct Commissions Paid'),
            )

    def action_mark_commissions_paid_manually(self):
        """Manual action to mark commissions paid for this vendor bill"""
        self.ensure_one()

        if self.move_type != 'in_invoice':
            raise UserError(_('This action is only for vendor bills.'))

        if not self.invoice_origin:
            raise UserError(_('This bill is not linked to a purchase order.'))

        # Find the PO
        po = self.env['purchase.order'].search([
            ('name', '=', self.invoice_origin)
        ], limit=1)

        if not po or not po.claim_ids:
            raise UserError(_('This bill is not linked to a commission purchase order.'))

        # Mark commissions paid manually
        self._mark_commissions_paid()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Commissions have been marked as paid.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_commissions(self):
        """View commissions for this invoice"""
        self.ensure_one()
        return {
            'name': _('Commissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.commission',
            'view_mode': 'list,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {'default_invoice_id': self.id}
        }
