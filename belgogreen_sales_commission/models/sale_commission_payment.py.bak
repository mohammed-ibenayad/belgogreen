# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleCommissionPayment(models.Model):
    _name = 'sale.commission.payment'
    _description = 'Commission Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    commission_ids = fields.Many2many(
        'sale.commission',
        string='Commissions',
        domain="[('payment_status', 'in', ['unpaid', 'claimed', 'processing']), ('can_be_paid', '=', True), ('user_id', '=', user_id)]",
        help='Commissions included in this payment'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Beneficiary',
        required=True,
        tracking=True,
        help='The user receiving this payment'
    )

    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )

    # Linked claim and PO
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        readonly=True,
        help='Purchase order that generated this payment'
    )

    claim_ids = fields.Many2many(
        'sale.commission.claim',
        'payment_claim_rel',
        'payment_id', 'claim_id',
        string='Claims',
        readonly=True,
        help='Commission claims associated with this payment'
    )

    # Amount breakdown
    gross_amount = fields.Monetary(
        string='Gross Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Total commission amount before deductions'
    )

    deduction_amount = fields.Monetary(
        string='Deductions',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Total deduction amount'
    )

    payment_amount = fields.Monetary(
        string='Net Amount',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help='Amount to be paid after deductions'
    )

    # Keep for backwards compatibility but deprecated
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('cash', 'Cash'),
        ('other', 'Other')
    ], string='Payment Method', required=True, default='bank_transfer', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], string='State', default='draft', required=True, tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    commission_count = fields.Integer(
        string='Commission Count',
        compute='_compute_commission_count'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence and validate payment data"""
        for vals in vals_list:
            # Generate sequence
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.commission.payment') or _('New')

            # If PO is provided, auto-fill payment_amount from PO total
            if vals.get('purchase_order_id') and 'payment_amount' not in vals:
                po = self.env['purchase.order'].browse(vals['purchase_order_id'])
                vals['payment_amount'] = po.amount_total

            # If payment_amount not set, calculate from commissions
            elif 'payment_amount' not in vals and vals.get('commission_ids'):
                # Calculate from commissions (for manual creation)
                commission_ids = vals['commission_ids'][0][2] if vals['commission_ids'] else []
                if commission_ids:
                    commissions = self.env['sale.commission'].browse(commission_ids)
                    vals['payment_amount'] = sum(commissions.mapped('commission_amount'))

        payments = super(SaleCommissionPayment, self).create(vals_list)

        # Link claims to payment
        for payment in payments:
            if payment.purchase_order_id and payment.purchase_order_id.mapped('claim_ids'):
                claims = payment.purchase_order_id.mapped('claim_ids')
                payment.claim_ids = claims
                claims.write({'payment_id': payment.id})

        return payments

    @api.depends('claim_ids', 'claim_ids.total_amount', 'claim_ids.total_deductions',
                 'commission_ids', 'commission_ids.commission_amount')
    def _compute_amounts(self):
        """Compute gross and deduction amounts"""
        for payment in self:
            if payment.claim_ids:
                # From claims (preferred source)
                payment.gross_amount = sum(payment.claim_ids.mapped('total_amount'))
                payment.deduction_amount = sum(payment.claim_ids.mapped('total_deductions'))
            else:
                # From commissions (manual payment without claims)
                payment.gross_amount = sum(payment.commission_ids.mapped('commission_amount'))
                payment.deduction_amount = 0

    @api.depends('commission_ids', 'commission_ids.commission_amount')
    def _compute_total_amount(self):
        """Compute total payment amount (deprecated, use payment_amount instead)"""
        for payment in self:
            payment.total_amount = sum(payment.commission_ids.mapped('commission_amount'))

    @api.depends('commission_ids')
    def _compute_commission_count(self):
        """Count commissions in this payment"""
        for payment in self:
            payment.commission_count = len(payment.commission_ids)

    def action_confirm(self):
        """Confirm the payment"""
        for payment in self:
            if not payment.commission_ids:
                raise UserError(_('Please add at least one commission to this payment.'))
            payment.state = 'confirmed'
            payment.commission_ids.write({'payment_status': 'processing'})

    def action_mark_paid(self):
        """Mark payment as paid and update commissions"""
        for payment in self:
            if payment.state != 'confirmed':
                raise UserError(_('Only confirmed payments can be marked as paid.'))

            payment.state = 'paid'
            payment.commission_ids.write({
                'payment_status': 'paid',
                'payment_date': payment.payment_date,
                'payment_id': payment.id
            })

    def action_cancel(self):
        """Cancel the payment"""
        for payment in self:
            if payment.state == 'paid':
                raise UserError(_('Cannot cancel a payment that is already marked as paid.'))

            payment.state = 'cancelled'
            # Reset commissions to unpaid if they were in processing
            payment.commission_ids.filtered(
                lambda c: c.payment_status == 'processing'
            ).write({'payment_status': 'unpaid'})

    def action_view_commissions(self):
        """View commissions in this payment"""
        self.ensure_one()
        return {
            'name': _('Commissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.commission',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.commission_ids.ids)],
            'context': {'default_payment_id': self.id}
        }
