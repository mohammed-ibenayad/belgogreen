# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleCommissionClaim(models.Model):
    _name = 'sale.commission.claim'
    _description = 'Commission Payment Claim'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'claim_date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    commission_ids = fields.Many2many(
        'sale.commission',
        string='Claimed Commissions',
        help='Commissions being claimed for payment'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Claimant',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        help='The user claiming the commissions'
    )

    claim_date = fields.Datetime(
        string='Claim Date',
        required=True,
        default=fields.Datetime.now,
        readonly=True
    )

    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente'),
        ('approved', 'Approuvée'),
        ('rejected', 'Rejetée')
    ], string='State', default='draft', required=True, tracking=True,
       help='Brouillon: En préparation | En attente: En attente de révision | Approuvée: Prête à payer | Rejetée: Refusée')

    processed_by = fields.Many2one(
        'res.users',
        string='Processed By',
        readonly=True,
        help='The admin who processed this claim'
    )

    processed_date = fields.Datetime(
        string='Processed Date',
        readonly=True
    )

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

    # Deduction fields
    mandatory_deduction_ids = fields.Many2many(
        'commission.deduction',
        'claim_mandatory_deduction_rel',
        'claim_id', 'deduction_id',
        string='Mandatory Deductions',
        compute='_compute_deductions',
        store=True,
        help="Auto-applied mandatory deductions"
    )

    optional_deduction_ids = fields.Many2many(
        'commission.deduction',
        'claim_optional_deduction_rel',
        'claim_id', 'deduction_id',
        string='Optional Deductions',
        compute='_compute_deductions',
        store=True,
        readonly=False,
        help="User-selected optional deductions"
    )

    all_deduction_ids = fields.Many2many(
        'commission.deduction',
        'claim_all_deduction_rel',
        'claim_id', 'deduction_id',
        string='All Deductions',
        compute='_compute_totals',
        store=True,
        help="All deductions (mandatory + optional)"
    )

    total_mandatory_deductions = fields.Monetary(
        string='Total Mandatory Deductions',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )

    total_optional_deductions = fields.Monetary(
        string='Total Optional Deductions',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )

    total_deductions = fields.Monetary(
        string='Total Deductions',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )

    net_amount = fields.Monetary(
        string='Net Amount',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Amount after all deductions'
    )

    # Purchase Order fields
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        readonly=True,
        copy=False,
        help='Purchase order generated from this claim'
    )

    purchase_order_state = fields.Selection(
        related='purchase_order_id.state',
        string='PO Status',
        store=True
    )

    # Simplified state - no payment tracking at claim level
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string='State', default='draft', required=True, tracking=True,
       help='Draft: Being prepared | Pending: Awaiting manager approval | '
            'Approved: Manager approved and PO created | Rejected: Denied | Cancelled: Cancelled')

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence and notify admins"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.commission.claim') or _('New')

        results = super(SaleCommissionClaim, self).create(vals_list)
        for result in results:
            result._notify_admins()
        return results

    @api.depends('commission_ids', 'commission_ids.commission_amount')
    def _compute_total_amount(self):
        """Compute total claimed amount"""
        for claim in self:
            claim.total_amount = sum(claim.commission_ids.mapped('commission_amount'))

    @api.depends('commission_ids')
    def _compute_commission_count(self):
        """Count commissions in this claim"""
        for claim in self:
            claim.commission_count = len(claim.commission_ids)

    @api.depends('user_id', 'state')
    def _compute_deductions(self):
        """Auto-load deductions based on claim state"""
        for claim in self:
            if claim.user_id and claim.state in ['draft', 'pending']:
                # Load pending mandatory deductions
                mandatory = self.env['commission.deduction'].search([
                    ('user_id', '=', claim.user_id.id),
                    ('deduction_category', '=', 'mandatory'),
                    ('state', '=', 'pending'),
                    ('company_id', '=', claim.company_id.id)
                ])
                claim.mandatory_deduction_ids = mandatory
                # Optional deductions are manually selected, don't auto-load in draft/pending
            elif claim.id:
                # For approved/rejected claims, load all deductions that were applied to this claim
                mandatory = self.env['commission.deduction'].search([
                    ('claim_id', '=', claim.id),
                    ('deduction_category', '=', 'mandatory'),
                ])
                claim.mandatory_deduction_ids = mandatory

                optional = self.env['commission.deduction'].search([
                    ('claim_id', '=', claim.id),
                    ('deduction_category', '=', 'optional'),
                ])
                claim.optional_deduction_ids = optional
            else:
                claim.mandatory_deduction_ids = False
                claim.optional_deduction_ids = False

    @api.depends('commission_ids', 'commission_ids.commission_amount',
                 'mandatory_deduction_ids', 'mandatory_deduction_ids.amount',
                 'optional_deduction_ids', 'optional_deduction_ids.amount')
    def _compute_totals(self):
        """Compute all totals including deductions"""
        for claim in self:
            # Gross commission amount
            claim.total_amount = sum(claim.commission_ids.mapped('commission_amount'))

            # Mandatory deductions
            claim.total_mandatory_deductions = sum(claim.mandatory_deduction_ids.mapped('amount'))

            # Optional deductions
            claim.total_optional_deductions = sum(claim.optional_deduction_ids.mapped('amount'))

            # Total deductions
            claim.total_deductions = claim.total_mandatory_deductions + claim.total_optional_deductions

            # All deductions combined
            claim.all_deduction_ids = claim.mandatory_deduction_ids | claim.optional_deduction_ids

            # Net amount
            claim.net_amount = claim.total_amount - claim.total_deductions


    @api.constrains('net_amount', 'state')
    def _check_net_amount_positive(self):
        """Ensure net amount is positive when submitting"""
        for claim in self:
            if claim.state == 'pending' and claim.net_amount < 0:
                raise ValidationError(
                    _("Cannot submit claim with negative net amount.\n\n"
                      "Gross commissions: %(gross)s\n"
                      "Mandatory deductions: -%(mandatory)s\n"
                      "Optional deductions: -%(optional)s\n"
                      "────────────────────────────\n"
                      "Net amount: %(net)s\n\n"
                      "Please contact your manager to resolve deduction issues.") % {
                        'gross': claim.total_amount,
                        'mandatory': claim.total_mandatory_deductions,
                        'optional': claim.total_optional_deductions,
                        'net': claim.net_amount
                    }
                )

    def action_submit(self):
        """Submit claim for approval"""
        self.ensure_one()
        if not self.commission_ids:
            raise UserError(_('Please select at least one commission to claim.'))
        if self.net_amount <= 0:
            raise UserError(_('Net claim amount must be positive.'))

        # Update commission status to claimed
        self.commission_ids.write({'status': 'claimed'})

        self.write({'state': 'pending'})
        self._notify_admins()
        return True

    def action_delete_draft(self):
        """Delete draft claim and return to list view"""
        self.ensure_one()

        # Verify claim is in draft state
        if self.state != 'draft':
            raise UserError(_('Only draft claims can be deleted.'))

        # Verify user owns the claim
        if self.user_id.id != self.env.user.id:
            raise UserError(_('You can only delete your own claims.'))

        # Delete the claim
        self.unlink()

        # Return to the claims list
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Claims'),
            'res_model': 'sale.commission.claim',
            'view_mode': 'list,form',
            'domain': [('user_id', '=', self.env.user.id)],
            'context': {'search_default_my_claims': 1},
            'target': 'current',
        }

    def action_approve(self):
        """Approve claim(s) and create draft PO

        Supports both single claim and batch claims (multiple claims from same employee)
        Includes any mandatory deductions added after claim submission.
        """
        # Validate all claims are in pending state
        if any(claim.state != 'pending' for claim in self):
            raise UserError(_('All claims must be in pending state to approve.'))

        # Validate no existing POs
        if any(claim.purchase_order_id for claim in self):
            raise UserError(_('Some claims already have purchase orders.'))

        # Get the user (all claims should be from same user)
        user = self.mapped('user_id')
        if len(user) > 1:
            raise UserError(_('All claims must be from the same user.'))
        user = user[0]

        # Check for any NEW mandatory deductions added after claim submission
        # These are pending mandatory deductions not yet linked to any claim
        new_mandatory_deductions = self.env['commission.deduction'].search([
            ('user_id', '=', user.id),
            ('state', '=', 'pending'),
            ('deduction_category', '=', 'mandatory'),
            ('claim_id', '=', False)  # Not yet linked to any claim
        ])

        # Add new mandatory deductions to all claims
        if new_mandatory_deductions:
            for claim in self:
                # Link new deductions to this claim's all_deduction_ids
                # Note: We modify all_deduction_ids through mandatory_deduction_ids
                claim.write({
                    'mandatory_deduction_ids': [(4, deduction.id) for deduction in new_mandatory_deductions]
                })

        # Ensure user is set up as vendor (use first claim's user, already validated same user in _create_purchase_order)
        vendor = self[0]._ensure_user_as_vendor()

        # Create draft Purchase Order (handles batch internally)
        po = self._create_purchase_order(vendor)

        # IMPORTANT: Mark deductions as applied BEFORE changing state to 'approved'
        # This is critical because changing state triggers _compute_deductions which clears
        # mandatory_deduction_ids when state is not 'draft' or 'pending', which in turn
        # empties all_deduction_ids through _compute_totals
        for claim in self:
            claim.all_deduction_ids.write({
                'state': 'applied',
                'claim_id': claim.id,
                'purchase_order_id': po.id
            })

        # Update all claims state (PO already linked by _create_purchase_order)
        # This MUST come after marking deductions to avoid computed field recalculation bug
        self.write({
            'state': 'approved',
            'processed_by': self.env.user.id,
            'processed_date': fields.Datetime.now(),
        })

        # Notify claimants
        for claim in self:
            claim._notify_claimant('approved')

        # Open PO for manager to review
        return {
            'name': _('Review Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reject(self):
        """Reject the claim and reset deductions"""
        for claim in self:
            # Reset deductions to pending if they were applied
            if claim.all_deduction_ids:
                claim.all_deduction_ids.filtered(lambda d: d.state == 'applied').write({
                    'state': 'pending',
                    'claim_id': False,
                    'purchase_order_id': False
                })

            claim.write({
                'state': 'rejected',
                'processed_by': self.env.user.id,
                'processed_date': fields.Datetime.now()
            })
            claim.commission_ids.write({'status': 'unpaid'})

            # Send notification to claimant
            claim._notify_claimant('rejected')

    def _notify_admins(self):
        """Notify administrators about new claim"""
        try:
            admin_group = self.env['res.groups'].search([('name', '=', 'Admin')], limit=1)
            if not admin_group:
                return
            admins = self.env['res.users'].search([
                ('group_ids', 'in', admin_group.ids),
                ('company_ids', 'in', self.company_id.ids)
            ])

            for admin in admins:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=admin.id,
                    summary=_('New commission claim: %s') % self.name,
                    note=_('User %(user)s has claimed %(count)s commission(s) totaling %(amount)s %(currency)s') % {
                        'user': self.user_id.name,
                        'count': self.commission_count,
                        'amount': self.total_amount,
                        'currency': self.currency_id.name
                    }
                )
        except Exception:
            # If group doesn't exist or other error, continue without notification
            pass

    def _notify_claimant(self, decision):
        """Notify claimant about claim decision"""
        message = _('Your commission claim %s has been %s.') % (self.name, decision)

        self.message_post(
            body=message,
            subject=_('Commission Claim %s') % decision.title(),
            partner_ids=[self.user_id.partner_id.id],
            message_type='notification'
        )

    def action_view_commissions(self):
        """View commissions in this claim"""
        self.ensure_one()
        return {
            'name': _('Claimed Commissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.commission',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.commission_ids.ids)],
            'context': {'default_user_id': self.user_id.id}
        }

    def action_view_purchase_order(self):
        """View related purchase order"""
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError(_('No purchase order has been created yet.'))

        return {
            'name': _('Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def _ensure_user_as_vendor(self):
        """Ensure user has a vendor/partner record"""
        self.ensure_one()

        partner = self.user_id.partner_id
        if not partner:
            raise UserError(_('User %s does not have a linked partner record.') % self.user_id.name)

        # Ensure partner is set as supplier
        if not partner.supplier_rank:
            partner.write({'supplier_rank': 1})

        return partner

    def _create_purchase_order(self, vendor):
        """Create draft purchase order for commission payment with deduction lines

        Supports both single claim and batch claims (multiple claims from same employee)
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

        # Validate all claims are from same user
        users = self.mapped('user_id')
        if len(users) > 1:
            raise UserError(_(
                'Cannot create purchase order for claims from different employees.\n'
                'All claims must belong to the same employee.\n\n'
                'Selected claims by employee:\n%s'
            ) % '\n'.join([f'- {u.name}: {self.filtered(lambda c: c.user_id == u).mapped("name")}'
                           for u in users]))

        # Calculate totals
        total_gross = sum(self.mapped('total_amount'))
        total_deductions = sum(self.mapped('total_deductions'))

        # Create PO
        po_vals = {
            'partner_id': vendor.id,
            'origin': ', '.join(self.mapped('name')),
            'state': 'draft',
            'company_id': self[0].company_id.id,
            'currency_id': self[0].currency_id.id,
            'note': self._generate_batch_po_notes(),
        }

        po = self.env['purchase.order'].create(po_vals)

        # Link all claims to this PO
        self.write({'purchase_order_id': po.id})

        # Create main PO line with total gross commission amount
        line_name = _('Commission Payment')

        self.env['purchase.order.line'].create({
            'order_id': po.id,
            'product_id': product.id,
            'name': line_name,
            'product_qty': 1,
            'price_unit': total_gross,
            'date_planned': fields.Date.today(),
        })

        # Create negative PO lines for each deduction from all claims
        for claim in self:
            for deduction in claim.all_deduction_ids:
                # Get human-readable deduction type name
                deduction_type_name = dict(deduction._fields['deduction_type'].selection).get(
                    deduction.deduction_type,
                    deduction.deduction_type
                )

                # Include claim reference if batch
                if len(self) > 1:
                    deduction_line_name = _('Deduction: %s - %s (Claim: %s)') % (
                        deduction_type_name,
                        deduction.name,
                        claim.name
                    )
                else:
                    deduction_line_name = _('Deduction: %s - %s') % (deduction_type_name, deduction.name)

                self.env['purchase.order.line'].create({
                    'order_id': po.id,
                    'product_id': deduction_product.id,  # Use deduction product with 0% VAT
                    'name': deduction_line_name,
                    'product_qty': 1,
                    'price_unit': -deduction.amount,
                    'date_planned': fields.Date.today(),
                })

        return po

    def _generate_po_notes(self):
        """Generate notes for PO with deduction breakdown (single claim - deprecated, use _generate_batch_po_notes)"""
        self.ensure_one()
        return self._generate_batch_po_notes()

    def _generate_batch_po_notes(self):
        """Generate notes for PO with commission list and deduction breakdown"""
        lines = []

        # List all commissions - format: COM/00004: 373.94 € - Customer Name (only if customer exists)
        all_commissions = self.mapped('commission_ids')
        for commission in all_commissions:
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

