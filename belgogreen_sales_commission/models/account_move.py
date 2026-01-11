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

    def write(self, vals):
        """Override write to mark commissions paid when vendor bill is paid"""
        # Store previous payment states before write
        # This is needed to detect payment state changes that happen via reconciliation
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
                # Mark commissions paid for vendor bills
                # This works for both hierarchical and manually created commissions
                if move.move_type == 'in_invoice':
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
