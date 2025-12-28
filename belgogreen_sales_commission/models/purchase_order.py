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

    commission_ids = fields.Many2many(
        'sale.commission',
        'purchase_order_commission_rel',
        'purchase_order_id',
        'commission_id',
        string='Direct Commissions',
        readonly=True,
        help='Commissions paid directly via this PO (without claims)'
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
        """Override to update commission status when PO is confirmed"""
        res = super(PurchaseOrder, self).button_confirm()

        for po in self:
            # Handle claim-based commissions
            if po.claim_ids:
                # Get all commissions from all claims
                all_commissions = po.claim_ids.mapped('commission_ids')
                # Update commission status to processing
                all_commissions.write({'status': 'processing'})

            # Handle direct commissions (no claims)
            if po.commission_ids:
                # Already in processing status from action_create_po_from_commissions
                # Just ensure consistency
                po.commission_ids.filtered(lambda c: c.status != 'processing').write({'status': 'processing'})

        return res

    def button_cancel(self):
        """Override to handle claim cancellation and reset deductions"""
        # Store claims and direct commissions before cancellation
        claims_to_reset = {}
        direct_commissions_to_reset = {}

        for po in self:
            # Handle claim-based commissions
            if po.claim_ids:
                # Store claims and their deductions
                claims_to_reset[po.id] = {
                    'claims': po.claim_ids,
                    'deductions': po.claim_ids.mapped('all_deduction_ids').filtered(
                        lambda d: d.state == 'applied' and d.purchase_order_id == po
                    )
                }

            # Handle direct commissions (no claims)
            if po.commission_ids:
                direct_commissions_to_reset[po.id] = po.commission_ids

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

            # Reset direct commissions to unpaid
            if po.id in direct_commissions_to_reset:
                commissions = direct_commissions_to_reset[po.id]
                commissions.write({'status': 'unpaid'})

                # Log message on first commission
                if commissions:
                    commissions[0].message_post(
                        body=_('Purchase Order %s was cancelled. %s commission(s) reset to unpaid.') % (po.name, len(commissions)),
                        subject=_('PO Cancelled - Commissions Reset'),
                    )

        return res
