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

    # Status
    status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('claimed', 'Claimed'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='unpaid', required=True, tracking=True,
       help='Unpaid: Ready to claim | Claimed: In claim | Approved: Claim approved | '
            'Processing: Awaiting payment | Paid: Payment received')

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

    # Computed fields for references
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        compute='_compute_customer_id',
        store=True,
        help='Customer from the sale order'
    )

    po_bill_id = fields.Many2one(
        'account.move',
        string='Commission Bill',
        compute='_compute_po_bill_id',
        help='Vendor bill linked to the commission purchase order'
    )


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

    @api.depends('invoice_id.payment_state', 'status')
    def _compute_can_be_paid(self):
        """Check if commission can be paid"""
        for commission in self:
            if commission.plan_id.require_invoice_paid:
                commission.can_be_paid = (
                    commission.invoice_id and
                    commission.invoice_id.payment_state in ['paid', 'in_payment'] and
                    commission.status in ['unpaid', 'claimed', 'processing']
                )
            else:
                commission.can_be_paid = (
                    commission.status in ['unpaid', 'claimed', 'processing']
                )

    def _compute_claim_ids(self):
        """Find claims that include this commission"""
        for commission in self:
            claims = self.env['sale.commission.claim'].search([
                ('commission_ids', 'in', commission.id)
            ])
            commission.claim_ids = claims
            commission.claim_count = len(claims)

    @api.depends('sale_order_id', 'sale_order_id.partner_id')
    def _compute_customer_id(self):
        """Get customer from sale order"""
        for commission in self:
            commission.customer_id = commission.sale_order_id.partner_id if commission.sale_order_id else False

    def _compute_po_bill_id(self):
        """Get vendor bill linked to commission PO"""
        for commission in self:
            # Find the claim that includes this commission
            claim = self.env['sale.commission.claim'].search([
                ('commission_ids', 'in', commission.id),
                ('purchase_order_id', '!=', False)
            ], limit=1)

            if claim and claim.purchase_order_id:
                # Find vendor bill linked to the PO
                bill = self.env['account.move'].search([
                    ('invoice_origin', '=', claim.purchase_order_id.name),
                    ('move_type', '=', 'in_invoice')
                ], limit=1)
                commission.po_bill_id = bill
            else:
                commission.po_bill_id = False

    def action_cancel(self):
        """Cancel commission"""
        self.write({'status': 'cancelled'})

    def action_claim_payment(self):
        """Allow user to claim their commission"""
        self.ensure_one()
        if self.status == 'unpaid':
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

    def action_create_po_from_commissions(self):
        """
        Create Purchase Order from selected commissions (Manager action)
        This action is called from the commission list view when manager selects multiple commissions
        """
        # Check if user has commission manager rights
        if not self.env.user.has_group('belgogreen_sales_commission.group_commission_manager'):
            raise UserError(_('Only Commission Managers can create purchase orders from commissions.'))

        # Validate all commissions belong to the same user (beneficiary)
        users = self.mapped('user_id')
        if len(users) > 1:
            raise UserError(_(
                'Cannot create purchase order for commissions from different beneficiaries.\n'
                'All selected commissions must belong to the same employee.\n\n'
                'Selected commissions by employee:\n%s'
            ) % '\n'.join([f'- {u.name}: {len(self.filtered(lambda c: c.user_id == u))} commission(s)'
                           for u in users]))

        if not users:
            raise UserError(_('Please select at least one commission.'))

        # Check if any commissions already have claims
        commissions_with_claims = self.filtered(lambda c: c.claim_count > 0)
        if commissions_with_claims:
            raise UserError(_(
                'Some selected commissions already have claims.\n'
                'Please remove them from the selection or process their existing claims.\n\n'
                'Commissions with existing claims:\n%s'
            ) % '\n'.join([f'- {c.name}: {c.claim_count} claim(s)'
                           for c in commissions_with_claims]))

        # Validate all commissions are in 'unpaid' status only
        # (claimed commissions should already have claims)
        invalid_commissions = self.filtered(lambda c: c.status != 'unpaid')
        if invalid_commissions:
            raise UserError(_(
                'Cannot create purchase order for commissions that are not in "Unpaid" status.\n\n'
                'Invalid commissions:\n%s'
            ) % '\n'.join([f'- {c.name}: {dict(c._fields["status"].selection).get(c.status)}'
                           for c in invalid_commissions]))

        # Check if all commissions can be paid (invoice paid requirement)
        unpayable_commissions = self.filtered(lambda c: not c.can_be_paid)
        if unpayable_commissions:
            raise UserError(_(
                'Some selected commissions cannot be paid yet (invoice not paid).\n\n'
                'Unpayable commissions:\n%s'
            ) % '\n'.join([f'- {c.name}: Invoice {c.invoice_id.name if c.invoice_id else "N/A"} '
                           f'({dict(c.invoice_id._fields["payment_state"].selection).get(c.invoice_id.payment_state) if c.invoice_id else "No invoice"})'
                           for c in unpayable_commissions]))

        # Create claim(s) for these commissions
        # Group commissions by user (already validated to be same user)
        user = users[0]

        # Create a single claim for all commissions
        claim = self.env['sale.commission.claim'].create({
            'user_id': user.id,
            'commission_ids': [(6, 0, self.ids)],
        })

        # Submit the claim (changes state from draft to pending)
        claim.action_submit()

        # Approve the claim and create PO
        # This will call the existing action_approve method which creates the PO
        return claim.action_approve()
