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
        required=False,
        tracking=True,
        help='The role of the user in this commission. Not required for manual commissions.'
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
        required=False,
        help='Commission plan used for automatic commissions. Not required for manual commissions.'
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

    linked_sale_order_ids = fields.Many2many(
        'sale.order',
        'commission_sale_order_rel',
        'commission_id', 'order_id',
        string='Linked Sale Orders',
        help='For manual commissions with multiple sale orders'
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

    sale_order_display = fields.Char(
        string='Sale Order(s)',
        compute='_compute_sale_order_display',
        help='Display single sale order or count of multiple orders'
    )

    po_bill_id = fields.Integer(
        string='Commission Bill ID',
        compute='_compute_po_bill_id',
        help='Vendor bill ID linked to the commission purchase order'
    )

    purchase_order_id = fields.Integer(
        string='Purchase Order ID',
        compute='_compute_purchase_order_id',
        help='Purchase order ID for this commission payment'
    )


    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence for commission reference"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.commission') or _('New')
        return super(SaleCommission, self).create(vals_list)

    @api.constrains('plan_id', 'is_adjustment')
    def _check_plan_required(self):
        """Ensure plan_id is set for automatic commissions (non-manual)"""
        for commission in self:
            if not commission.is_adjustment and not commission.plan_id:
                raise UserError(_(
                    'Commission Plan is required for automatic commissions.\n'
                    'Only manual commissions (created by managers) can have no plan.'
                ))

    @api.constrains('role_id', 'is_adjustment')
    def _check_role_required(self):
        """Ensure role_id is set for automatic commissions (non-manual)"""
        for commission in self:
            if not commission.is_adjustment and not commission.role_id:
                raise UserError(_(
                    'Role is required for automatic commissions.\n'
                    'Only manual commissions (created by managers) can have no role.'
                ))

    @api.depends('percentage_override', 'plan_id', 'role_id', 'commission_type', 'is_adjustment')
    def _compute_commission_percentage(self):
        """
        Compute the effective commission percentage based on:
        - Manual override (if set)
        - Commission type (direct vs override)
        - Role configuration
        - For manual commissions: percentage is 0 (amount is set directly)
        """
        for commission in self:
            if commission.percentage_override:
                commission.commission_percentage = commission.percentage_override
            elif commission.is_adjustment:
                # Manual commissions: percentage is 0 (amount is set directly)
                commission.commission_percentage = 0.0
            elif commission.plan_id:
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
            else:
                commission.commission_percentage = 0.0

    @api.depends('base_amount', 'commission_percentage', 'is_adjustment')
    def _compute_commission_amount(self):
        """Compute commission amount based on base amount and percentage
        For manual commissions (is_adjustment=True), preserve the stored amount"""
        for commission in self:
            # Skip computation for manual commissions - keep stored amount
            if commission.is_adjustment and commission.commission_amount:
                continue
            # Normal commission: calculate from base amount and percentage
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

    @api.depends('sale_order_id', 'sale_order_id.partner_id', 'is_adjustment', 'linked_sale_order_ids')
    def _compute_customer_id(self):
        """Get customer from sale order
        For manual commissions with multiple sale orders, don't set a customer
        """
        for commission in self:
            # Manual commission with multiple sale orders - no specific customer
            if commission.is_adjustment and commission.linked_sale_order_ids:
                commission.customer_id = False
            # Regular commission or manual with single sale order
            else:
                commission.customer_id = commission.sale_order_id.partner_id if commission.sale_order_id else False

    @api.depends('sale_order_id', 'linked_sale_order_ids')
    def _compute_sale_order_display(self):
        """Display sale order info for list view
        Shows single order name or count of multiple orders
        """
        for commission in self:
            if commission.linked_sale_order_ids:
                # Multiple sale orders
                count = len(commission.linked_sale_order_ids)
                commission.sale_order_display = _('%s Orders') % count
            elif commission.sale_order_id:
                # Single sale order
                commission.sale_order_display = commission.sale_order_id.name
            else:
                commission.sale_order_display = ''

    def _compute_purchase_order_id(self):
        """Get purchase order for this commission"""
        for commission in self:
            # Use sudo() to allow sales users to view commission details
            # without requiring purchase order access
            po = self.env['purchase.order'].sudo().search([
                ('commission_ids', 'in', commission.id)
            ], limit=1)

            if not po:
                # Check if commission is linked via a claim
                claim = self.env['sale.commission.claim'].sudo().search([
                    ('commission_ids', 'in', commission.id),
                    ('purchase_order_id', '!=', False)
                ], limit=1)
                po = claim.purchase_order_id if claim else False

            commission.purchase_order_id = po.id if po else False

    def _compute_po_bill_id(self):
        """Get vendor bill linked to commission PO"""
        for commission in self:
            bill_id = False
            if commission.purchase_order_id:
                # Get the PO name using sudo
                po = self.env['purchase.order'].sudo().browse(commission.purchase_order_id)
                if po.exists():
                    # Find vendor bill linked to the PO
                    bill = self.env['account.move'].sudo().search([
                        ('invoice_origin', '=', po.name),
                        ('move_type', '=', 'in_invoice')
                    ], limit=1)
                    bill_id = bill.id if bill else False

            commission.po_bill_id = bill_id

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

    def action_view_purchase_order(self):
        """View the purchase order for this commission"""
        self.ensure_one()

        if not self.purchase_order_id:
            raise UserError(_('No purchase order found for this commission.'))

        # Use sudo() to allow sales users to view PO (read-only for them)
        return {
            'name': _('Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'force_readonly': True}  # Force read-only for sales users
        }

    def action_view_po_bill(self):
        """View the vendor bill for this commission"""
        self.ensure_one()

        if not self.po_bill_id:
            raise UserError(_('No vendor bill found for this commission.'))

        # Use sudo() to allow sales users to view bill (read-only for them)
        return {
            'name': _('Commission Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.po_bill_id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'force_readonly': True}  # Force read-only for sales users
        }

    def action_view_sale_order(self):
        """View the sale order for this commission"""
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError(_('No sale order found for this commission.'))

        return {
            'name': _('Sale Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_po_from_commissions(self):
        """
        Create Purchase Order directly from selected commissions (Manager action)
        This bypasses the claim workflow - managers can pay commissions proactively
        without requiring users to claim first.
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

        # Validate all commissions are in 'unpaid' status
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

        # Get the user and ensure they are set up as vendor
        user = users[0]
        vendor = self._ensure_commission_user_as_vendor(user)

        # Create PO directly (no claim, no deductions)
        po = self._create_po_for_commissions(vendor)

        # Update commission status to processing
        self.write({'status': 'processing'})

        # Open the created PO
        return {
            'name': _('Commission Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _ensure_commission_user_as_vendor(self, user):
        """Ensure commission user has a vendor/partner record"""
        partner = user.partner_id
        if not partner:
            raise UserError(_('User %s does not have a linked partner record.') % user.name)

        # Ensure partner is set as supplier
        if not partner.supplier_rank:
            partner.write({'supplier_rank': 1})

        return partner

    def _create_po_for_commissions(self, vendor):
        """
        Create draft purchase order for commission payment (without claim)
        This is used when managers create POs directly without requiring user claims.
        Includes mandatory deductions for the user.
        """
        # Get commission service product
        product = self.env.ref('belgogreen_sales_commission.product_commission_service', raise_if_not_found=False)
        if not product:
            raise UserError(_(
                'Commission service product not found. '
                'Please contact your administrator to configure the commission service product.'
            ))

        # Get commission deduction product (with 0% VAT)
        deduction_product = self.env.ref('belgogreen_sales_commission.product_commission_deduction', raise_if_not_found=False)
        if not deduction_product:
            raise UserError(_(
                'Commission deduction product not found. '
                'Please contact your administrator to configure the commission deduction product.'
            ))

        # Get the user (all commissions belong to same user, validated earlier)
        user = self.mapped('user_id')[0]

        # Fetch all pending mandatory deductions for this user
        mandatory_deductions = self.env['commission.deduction'].search([
            ('user_id', '=', user.id),
            ('state', '=', 'pending'),
            ('deduction_category', '=', 'mandatory')
        ])

        # Calculate total commission amount
        total_amount = sum(self.mapped('commission_amount'))
        total_deductions = sum(mandatory_deductions.mapped('amount'))

        # Create PO
        po_vals = {
            'partner_id': vendor.id,
            'origin': ', '.join(self.mapped('name')),
            'state': 'draft',
            'company_id': self[0].company_id.id,
            'currency_id': self[0].currency_id.id,
            'note': self._generate_po_notes_for_commissions(),
        }

        po = self.env['purchase.order'].create(po_vals)

        # Link commissions to PO
        po.write({'commission_ids': [(6, 0, self.ids)]})

        # Create main PO line with total commission amount
        line_name = _('Commission Payment - %s') % vendor.name

        self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': product.id,
            'name': line_name,
            'product_qty': 1,
            'price_unit': total_amount,
            'date_planned': fields.Date.today(),
        })

        # Create negative PO lines for each mandatory deduction
        for deduction in mandatory_deductions:
            # Get human-readable deduction type name
            deduction_type_name = dict(deduction._fields['deduction_type'].selection).get(
                deduction.deduction_type,
                deduction.deduction_type
            )

            deduction_line_name = _('Deduction: %s - %s') % (deduction_type_name, deduction.name)

            self.env['purchase.order.line'].create({
                'order_id': po.id,
                'product_id': deduction_product.id,  # Use deduction product with 0% VAT
                'name': deduction_line_name,
                'product_qty': 1,
                'price_unit': -deduction.amount,
                'date_planned': fields.Date.today(),
            })

        # Mark deductions as applied and link to PO
        # Note: claim_id is False since this is direct PO creation without claim
        mandatory_deductions.write({
            'state': 'applied',
            'purchase_order_id': po.id,
            'claim_id': False,
        })

        return po

    def _generate_po_notes_for_commissions(self):
        """Generate notes for PO with commission list (no deductions - direct payment)"""
        lines = []
        for commission in self:
            if commission.customer_id:
                lines.append('%s: %s %s - %s' % (
                    commission.name,
                    commission.commission_amount,
                    self[0].currency_id.symbol,
                    commission.customer_id.name
                ))
            else:
                lines.append('%s: %s %s' % (
                    commission.name,
                    commission.commission_amount,
                    self[0].currency_id.symbol
                ))
        return '\n'.join(lines)
