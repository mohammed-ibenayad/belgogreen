# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
            move.commission_count = len(move.sudo().commission_ids)

    def write(self, vals):
        """Override write to mark commissions paid when vendor bill is paid"""
        # Store previous payment states before write
        # CRITICAL: Always track vendor bills because payment_state is a computed field
        # that can change due to reconciliation without being in vals!
        previous_states = {}
        for move in self:
            # Track ALL vendor bills (in_invoice) regardless of what's being written
            if move.move_type == 'in_invoice':
                previous_states[move.id] = move.payment_state
                _logger.info(
                    "Commission Payment: [BEFORE] Tracking vendor bill %s (ID: %s, Previous state: %s, vals keys: %s)",
                    move.name, move.id, move.payment_state, list(vals.keys())
                )

        result = super(AccountMove, self).write(vals)

        for move in self:
            # Only process vendor bills that we tracked
            if move.id not in previous_states:
                continue

            previous_payment_state = previous_states[move.id]
            current_payment_state = move.payment_state

            # Check if payment_state changed to paid
            payment_state_changed = (
                previous_payment_state != 'paid' and
                current_payment_state == 'paid'
            )

            _logger.info(
                "Commission Payment: [AFTER] Move %s (ID: %s) - Previous: %s, Current: %s, Changed: %s, Origin: %s",
                move.name, move.id,
                previous_payment_state,
                current_payment_state,
                payment_state_changed,
                move.invoice_origin or 'N/A'
            )

            if payment_state_changed:
                _logger.info(
                    "Commission Payment: ✅ Payment state changed! Triggering _mark_commissions_paid for %s",
                    move.name
                )
                move._mark_commissions_paid()

        return result

    def _mark_commissions_paid(self):
        """Mark commissions as paid when vendor bill is paid"""
        self.ensure_one()

        _logger.info(
            "Commission Payment: _mark_commissions_paid called for bill %s (ID: %s)",
            self.name, self.id
        )

        if not self.invoice_origin:
            _logger.warning(
                "Commission Payment: Bill %s has no invoice_origin, skipping",
                self.name
            )
            return

        _logger.info(
            "Commission Payment: Searching for PO with name '%s'",
            self.invoice_origin
        )

        # Find the PO
        po = self.env['purchase.order'].search([
            ('name', '=', self.invoice_origin)
        ], limit=1)

        if not po:
            _logger.warning(
                "Commission Payment: No PO found with name '%s', skipping",
                self.invoice_origin
            )
            return  # Not a commission payment

        po_sudo = po.sudo()

        _logger.info(
            "Commission Payment: Found PO %s (ID: %s), Claims: %s, Direct Commissions: %s",
            po.name, po.id, len(po_sudo.claim_ids), len(po_sudo.commission_ids)
        )

        # Check if this is a commission PO (either claim-based or direct)
        if not po_sudo.claim_ids and not po_sudo.commission_ids:
            _logger.info(
                "Commission Payment: PO %s has no claims or commissions, skipping",
                po.name
            )
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

        _logger.info(
            "Commission Payment: Found %s payable/receivable line(s) for bill %s",
            len(payable_line), self.name
        )

        # Get payments from reconciled lines
        payments = self.env['account.payment']
        if payable_line:
            # Get all matched debits/credits (reconciliation records)
            matched_lines = payable_line.mapped('matched_debit_ids.debit_move_id') | \
                           payable_line.mapped('matched_credit_ids.credit_move_id')

            _logger.info(
                "Commission Payment: Found %s matched line(s) from reconciliation",
                len(matched_lines)
            )

            # Get payment records from those move lines
            payment_moves = matched_lines.mapped('move_id')
            payments = self.env['account.payment'].search([
                ('move_id', 'in', payment_moves.ids)
            ])

            _logger.info(
                "Commission Payment: Found %s payment(s): %s (States: %s)",
                len(payments),
                ', '.join(payments.mapped('name')),
                ', '.join(payments.mapped('state'))
            )
        else:
            _logger.warning(
                "Commission Payment: No payable line found for bill %s",
                self.name
            )

        # Get ALL commissions (from claims or direct) - unified approach
        commissions = po_sudo.claim_ids.mapped('commission_ids') | po_sudo.commission_ids

        _logger.info(
            "Commission Payment: Found %s commission(s) to mark as paid: %s",
            len(commissions),
            ', '.join(commissions.mapped('name'))
        )

        if not commissions:
            _logger.warning(
                "Commission Payment: No commissions found for PO %s, skipping",
                po.name
            )
            return  # No commissions to mark as paid

        # Log commission details before update
        for comm in commissions:
            _logger.info(
                "Commission Payment: Commission %s (ID: %s) - Current status: %s, Amount: %s, User: %s",
                comm.name, comm.id, comm.status, comm.commission_amount, comm.user_id.name
            )

        # Update ALL commissions to paid (works for both claim-based and direct)
        payment_id_to_set = payments[0].id if payments else False
        payment_date_to_set = self.invoice_date or fields.Date.today()

        _logger.info(
            "Commission Payment: Updating commissions to paid - Payment ID: %s, Payment Date: %s",
            payment_id_to_set, payment_date_to_set
        )

        commissions.write({
            'status': 'paid',
            'payment_date': payment_date_to_set,
            'payment_id': payment_id_to_set,  # Link to first payment
        })

        _logger.info(
            "Commission Payment: Successfully updated %s commission(s) to paid status",
            len(commissions)
        )

        # Log success with appropriate message
        if po_sudo.claim_ids:
            # Claim-based payment
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
                    'claims': ', '.join(po_sudo.claim_ids.mapped('name')),
                },
                subject=_('Commissions Paid'),
            )
        else:
            # Direct payment (no claims)
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
                    'commissions': ', '.join(commissions.mapped('name')),
                },
                subject=_('Direct Commissions Paid'),
            )

    def action_mark_commissions_paid_manually(self):
        """Manual action to mark commissions paid for this vendor bill"""
        self.ensure_one()

        _logger.info(
            "Commission Payment: Manual action triggered for bill %s by user",
            self.name
        )

        if self.move_type != 'in_invoice':
            raise UserError(_('This action is only for vendor bills.'))

        if not self.invoice_origin:
            raise UserError(_('This bill is not linked to a purchase order.'))

        # Find the PO
        po = self.env['purchase.order'].search([
            ('name', '=', self.invoice_origin)
        ], limit=1)

        if not po or (not po.sudo().claim_ids and not po.sudo().commission_ids):
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

    def action_debug_commission_payment(self):
        """Debug action to analyze commission payment status"""
        self.ensure_one()

        _logger.info("=" * 80)
        _logger.info("COMMISSION PAYMENT DEBUG for Bill: %s (ID: %s)", self.name, self.id)
        _logger.info("=" * 80)

        _logger.info("Bill Details:")
        _logger.info("  - Type: %s", self.move_type)
        _logger.info("  - State: %s", self.state)
        _logger.info("  - Payment State: %s", self.payment_state)
        _logger.info("  - Invoice Origin: %s", self.invoice_origin)
        _logger.info("  - Amount Total: %s", self.amount_total)
        _logger.info("  - Invoice Date: %s", self.invoice_date)
        _logger.info("  - Has Reconciled Entries: %s", self.has_reconciled_entries)

        if self.invoice_origin:
            po = self.env['purchase.order'].search([('name', '=', self.invoice_origin)], limit=1)
            if po:
                po_sudo = po.sudo()
                _logger.info("Purchase Order Found:")
                _logger.info("  - PO: %s (ID: %s)", po.name, po.id)
                _logger.info("  - Claims: %s", len(po_sudo.claim_ids))
                _logger.info("  - Direct Commissions: %s", len(po_sudo.commission_ids))

                commissions = po_sudo.claim_ids.mapped('commission_ids') | po_sudo.commission_ids
                _logger.info("  - Total Commissions: %s", len(commissions))

                for comm in commissions:
                    _logger.info("  - Commission %s: Status=%s, Amount=%s, Payment ID=%s, Payment Date=%s",
                                comm.name, comm.status, comm.commission_amount,
                                comm.payment_id.id if comm.payment_id else None, comm.payment_date)
            else:
                _logger.warning("  - NO Purchase Order found with name: %s", self.invoice_origin)

        # Check payments
        payable_line = self.line_ids.filtered(
            lambda line: line.account_id.account_type in ('liability_payable', 'asset_receivable')
        )
        _logger.info("Payable/Receivable Lines: %s", len(payable_line))

        if payable_line:
            matched_lines = payable_line.mapped('matched_debit_ids.debit_move_id') | \
                           payable_line.mapped('matched_credit_ids.credit_move_id')
            _logger.info("Matched Lines from Reconciliation: %s", len(matched_lines))

            payment_moves = matched_lines.mapped('move_id')
            payments = self.env['account.payment'].search([('move_id', 'in', payment_moves.ids)])

            _logger.info("Payments Found: %s", len(payments))
            for payment in payments:
                _logger.info("  - Payment: %s (ID: %s, State: %s, Is Reconciled: %s)",
                            payment.name, payment.id, payment.state, payment.is_reconciled)

        _logger.info("=" * 80)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Debug Complete'),
                'message': _('Check server logs for detailed commission payment analysis.'),
                'type': 'info',
                'sticky': True,
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
