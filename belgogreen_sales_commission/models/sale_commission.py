# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleCommission(models.Model):
    _name = 'sale.commission'
    _description = 'Sales Commission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    # Basic Information
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        tracking=True,
        help='The user receiving this commission'
    )

    role_id = fields.Many2one(
        'sale.commission.role',
        string='Role',
        required=True,
        tracking=True,
        help='The role of the user in this commission'
    )

    commission_type = fields.Selection([
        ('direct', 'Direct Sale'),
        ('override', 'Override Commission')
    ], string='Commission Type', required=True, default='direct', tracking=True,
       help='Direct = user made the sale, Override = commission on subordinate\'s sale')

    # Related Sale and Invoice
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        ondelete='cascade',
        help='The sale order this commission is based on'
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        domain=[('move_type', '=', 'out_invoice')],
        help='The invoice this commission is based on'
    )

    # Commission Plan
    plan_id = fields.Many2one(
        'sale.commission.plan',
        string='Commission Plan',
        required=True
    )

    # Dates
    date = fields.Date(
        string='Commission Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )

    period = fields.Char(
        string='Period',
        help='Period this commission belongs to (e.g., 2025-Q1, 2025-11)'
    )

    # Amounts
    base_amount = fields.Monetary(
        string='Base Amount',
        required=True,
        currency_field='currency_id',
        help='The amount on which commission is calculated'
    )

    commission_percentage = fields.Float(
        string='Commission %',
        compute='_compute_commission_percentage',
        store=True,
        digits=(5, 2),
        help='The effective commission percentage applied'
    )

    percentage_override = fields.Float(
        string='Manual % Override',
        digits=(5, 2),
        tracking=True,
        help='Set a custom percentage for this commission (leave empty to use default)'
    )

    commission_amount = fields.Monetary(
        string='Commission Amount',
        compute='_compute_commission_amount',
        store=True,
        currency_field='currency_id',
        tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Payment Status
    payment_status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('claimed', 'Claimed'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], string='Payment Status', default='unpaid', required=True, tracking=True)

    payment_date = fields.Date(
        string='Payment Date',
        tracking=True
    )

    payment_id = fields.Many2one(
        'account.payment',
        string='Payment Record',
        readonly=True,
        help='The payment that paid this commission'
    )

    can_be_paid = fields.Boolean(
        string='Can Be Paid',
        compute='_compute_can_be_paid',
        store=True,
        help='True if invoice is paid and commission is unpaid'
    )

    # Claim relation
    claim_ids = fields.Many2many(
        'sale.commission.claim',
        string='Claims',
        compute='_compute_claim_ids',
        help='Claims that include this commission'
    )

    claim_count = fields.Integer(
        string='Claim Count',
        compute='_compute_claim_ids',
        help='Number of claims this commission belongs to'
    )

    # Additional Info
    is_adjustment = fields.Boolean(
        string='Is Adjustment',
        default=False,
        help='True if this is a manual adjustment commission'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], string='State', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence for commission reference"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.commission') or _('New')
        return super(SaleCommission, self).create(vals_list)

    @api.depends('percentage_override', 'plan_id', 'role_id', 'commission_type')
    def _compute_commission_percentage(self):
        """
        Compute the effective commission percentage based on:
        - Manual override (if set)
        - Commission type (direct vs override)
        - Role configuration
        """
        for commission in self:
            if commission.percentage_override:
                commission.commission_percentage = commission.percentage_override
            else:
                # Get role configuration for this plan and role
                config = self.env['hr.commission.role.config'].search([
                    ('plan_id', '=', commission.plan_id.id),
                    ('role_id', '=', commission.role_id.id)
                ], limit=1)

                if config:
                    # Use appropriate percentage based on commission type
                    if commission.commission_type == 'direct':
                        commission.commission_percentage = config.direct_sale_percentage
                    else:  # override
                        commission.commission_percentage = config.override_percentage
                else:
                    commission.commission_percentage = 0.0

    @api.depends('base_amount', 'commission_percentage')
    def _compute_commission_amount(self):
        """Compute commission amount based on base amount and percentage"""
        for commission in self:
            commission.commission_amount = (commission.base_amount * commission.commission_percentage) / 100.0

    @api.depends('invoice_id.payment_state', 'payment_status', 'state')
    def _compute_can_be_paid(self):
        """Check if commission can be paid"""
        for commission in self:
            if commission.plan_id.require_invoice_paid:
                commission.can_be_paid = (
                    commission.invoice_id and
                    commission.invoice_id.payment_state in ['paid', 'in_payment'] and
                    commission.payment_status in ['unpaid', 'claimed', 'processing'] and
                    commission.state == 'confirmed'
                )
            else:
                commission.can_be_paid = (
                    commission.payment_status in ['unpaid', 'claimed', 'processing'] and
                    commission.state == 'confirmed'
                )

    def _compute_claim_ids(self):
        """Find claims that include this commission"""
        for commission in self:
            claims = self.env['sale.commission.claim'].search([
                ('commission_ids', 'in', commission.id)
            ])
            commission.claim_ids = claims
            commission.claim_count = len(claims)

    def action_confirm(self):
        """Confirm commission"""
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        """Cancel commission"""
        self.write({
            'state': 'cancelled',
            'payment_status': 'cancelled'
        })

    def action_claim_payment(self):
        """Allow user to claim their commission"""
        self.ensure_one()
        if self.payment_status == 'unpaid':
            # Create a claim record in draft state
            # Commission will be marked as 'claimed' when claim is submitted
            claim = self.env['sale.commission.claim'].create({
                'user_id': self.user_id.id,
                'commission_ids': [(6, 0, [self.id])],
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.commission.claim',
                'res_id': claim.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_view_claim(self):
        """View the claim(s) this commission belongs to"""
        self.ensure_one()

        if self.claim_count == 1:
            # Open single claim
            return {
                'name': _('Commission Claim'),
                'type': 'ir.actions.act_window',
                'res_model': 'sale.commission.claim',
                'res_id': self.claim_ids[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Open list of claims
            return {
                'name': _('Commission Claims'),
                'type': 'ir.actions.act_window',
                'res_model': 'sale.commission.claim',
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.claim_ids.ids)],
            }

    def action_create_payment(self):
        """Create payment via claim (redirect to claim wizard)"""
        self.ensure_one()
        if not self.can_be_paid:
            raise UserError(_('This commission cannot be paid yet.'))

        # Redirect to claim wizard
        return {
            'name': _('Claim Commission'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.claim.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_commission_ids': [(6, 0, self.ids)],
            }
        }

    def action_view_payment(self):
        """View the payment that paid this commission"""
        self.ensure_one()

        if not self.payment_id:
            raise UserError(_('No payment found for this commission.'))

        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
