# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Deprecated - kept for backwards compatibility, use claim_ids instead
    commission_claim_id = fields.Many2one(
        'sale.commission.claim',
        string='Commission Claim',
        readonly=True,
        compute='_compute_commission_claim_id',
        store=True,
        help='Commission claim that generated this purchase order (deprecated, use claim_ids)'
    )

    claim_ids = fields.One2many(
        'sale.commission.claim',
        'purchase_order_id',
        string='Commission Claims',
        readonly=True,
        help='Commission claims associated with this purchase order'
    )

    @api.depends('claim_ids')
    def _compute_commission_claim_id(self):
        """Compute single claim for backwards compatibility"""
        for po in self:
            po.commission_claim_id = po.claim_ids[0] if po.claim_ids else False

    def write(self, vals):
        """Prevent editing commission PO lines"""
        for po in self:
            if po.claim_ids and po.state == 'draft':
                # Prevent editing PO lines for commission payments
                if 'order_line' in vals:
                    raise UserError(_(
                        'Cannot modify purchase order lines for commission payments.\n\n'
                        'This PO is generated from commission claims and contains:\n'
                        '- Gross commission amounts\n'
                        '- Deduction lines\n\n'
                        'If you need to make changes:\n'
                        '1. Cancel this PO\n'
                        '2. Adjust the claim deductions\n'
                        '3. Recreate the claim approval'
                    ))
        return super(PurchaseOrder, self).write(vals)

    def button_confirm(self):
        """Override to notify contractor and wait for invoice (NO auto-bill/payment creation)"""
        res = super(PurchaseOrder, self).button_confirm()

        for po in self:
            if po.claim_ids:
                # Update all claims to po_confirmed
                po.claim_ids.write({'state': 'po_confirmed'})

                # Get all commissions from all claims
                all_commissions = po.claim_ids.mapped('commission_ids')

                # Update commission status to processing (waiting for invoice)
                all_commissions.write({'payment_status': 'processing'})

                # Notify contractor to send invoice
                po._notify_contractor_send_invoice()

                # Create activity for accounting to watch for invoice
                po._create_invoice_receipt_activity()

        return res

    def _notify_contractor_send_invoice(self):
        """Notify contractor to send their invoice for approved commissions"""
        self.ensure_one()

        # Send email notification
        template = self.env.ref(
            'belgogreen_sales_commission.email_template_po_send_invoice_request',
            raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)

        # Log in PO chatter
        self.message_post(
            body=_(
                'Purchase Order confirmed and sent to contractor.\n\n'
                'Please send your invoice for:\n'
                '- Gross Commission: %(gross)s %(currency)s\n'
                '- Deductions: -%(deductions)s %(currency)s\n'
                '- Net Amount: %(net)s %(currency)s\n\n'
                'Once you receive their invoice, create a Vendor Bill from this PO.'
            ) % {
                'gross': sum(self.claim_ids.mapped('total_amount')),
                'deductions': sum(self.claim_ids.mapped('total_deductions')),
                'net': self.amount_total,
                'currency': self.currency_id.symbol,
            },
            subject=_('PO Sent - Awaiting Contractor Invoice'),
        )

    def _create_invoice_receipt_activity(self):
        """Create activity for accounting to receive and record invoice"""
        self.ensure_one()

        # Find accounting users
        try:
            accounting_group = self.env.ref('account.group_account_invoice')
            accountant = self.env['res.users'].search([
                ('groups_id', 'in', accounting_group.ids),
                ('company_ids', 'in', self.company_id.id)
            ], limit=1)

            if accountant:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=accountant.id,
                    summary=_('Record Contractor Invoice: %s') % self.name,
                    note=_(
                        'Waiting for invoice from %(contractor)s\n\n'
                        'Expected amount: %(amount)s %(currency)s\n'
                        'Commission claims: %(claims)s\n\n'
                        'When invoice received:\n'
                        '1. Click "Create Bill" button on this PO\n'
                        '2. Verify invoice amount matches PO\n'
                        '3. Post the bill\n'
                        '4. Create and post payment'
                    ) % {
                        'contractor': self.partner_id.name,
                        'amount': self.amount_total,
                        'currency': self.currency_id.symbol,
                        'claims': ', '.join(self.claim_ids.mapped('name')),
                    }
                )
        except Exception:
            # If group doesn't exist or other error, continue without activity
            pass

    def button_cancel(self):
        """Override to handle claim cancellation and reset deductions"""
        # Store claims before cancellation
        claims_to_reset = {}
        for po in self:
            if po.claim_ids:
                # Store claims and their deductions
                claims_to_reset[po.id] = {
                    'claims': po.claim_ids,
                    'deductions': po.claim_ids.mapped('all_deduction_ids').filtered(
                        lambda d: d.state == 'applied' and d.purchase_order_id == po
                    )
                }

        res = super(PurchaseOrder, self).button_cancel()

        # Reset claims and deductions after cancellation
        for po in self:
            if po.id in claims_to_reset:
                data = claims_to_reset[po.id]

                # Reset deductions to pending
                if data['deductions']:
                    data['deductions'].write({
                        'state': 'pending',
                        'claim_id': False,
                        'purchase_order_id': False
                    })

                # Reset claims to pending state
                data['claims'].write({
                    'state': 'pending',
                    'purchase_order_id': False,
                    'processed_by': False,
                    'processed_date': False
                })

                # Notify manager
                for claim in data['claims']:
                    claim.message_post(
                        body=_('Purchase Order %s was cancelled. Claim and deductions have been reset to pending.') % po.name,
                        subject=_('PO Cancelled - Claim Reset'),
                    )

        return res
