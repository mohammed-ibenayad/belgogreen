# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CommissionManualWizard(models.TransientModel):
    _name = 'commission.manual.wizard'
    _description = 'Manual Commission Creation Wizard'

    sale_order_ids = fields.Many2many(
        'sale.order',
        'commission_manual_wizard_sale_order_rel',
        'wizard_id', 'order_id',
        string='Sale Orders',
        required=True,
        domain=[('state', 'in', ['sale', 'done'])],
        help='Select one or more sale orders to link to this manual commission'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Commission Beneficiary',
        required=True,
        help='The user who will receive this commission'
    )

    role_id = fields.Many2one(
        'sale.commission.role',
        string='Role',
        required=True,
        help='The role of the commission beneficiary'
    )

    commission_type = fields.Selection([
        ('direct', 'Direct Sale'),
        ('override', 'Override Commission')
    ], string='Commission Type', required=True, default='direct',
       help='Type of commission being created')

    manual_amount = fields.Monetary(
        string='Commission Amount',
        required=True,
        currency_field='currency_id',
        help='The commission amount (specified manually, not calculated)'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    description = fields.Text(
        string='Reason / Notes',
        required=True,
        help='Explanation for this manual commission creation'
    )

    create_po_immediately = fields.Boolean(
        string='Create Purchase Order Immediately',
        default=False,
        help='If checked, a purchase order will be created immediately after commission creation'
    )

    sale_order_count = fields.Integer(
        string='Number of Sale Orders',
        compute='_compute_sale_order_count'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    @api.depends('sale_order_ids')
    def _compute_sale_order_count(self):
        for wizard in self:
            wizard.sale_order_count = len(wizard.sale_order_ids)

    @api.constrains('manual_amount')
    def _check_manual_amount(self):
        """Ensure manual amount is positive"""
        for wizard in self:
            if wizard.manual_amount <= 0:
                raise UserError(_('Commission amount must be greater than zero.'))

    def action_create_commission(self):
        """Create manual commission record"""
        self.ensure_one()

        # Check if user has commission manager rights
        if not self.env.user.has_group('belgogreen_sales_commission.group_commission_manager'):
            raise UserError(_('Only Commission Managers can create manual commissions.'))

        # Validate sale orders
        if not self.sale_order_ids:
            raise UserError(_('Please select at least one sale order.'))

        # Validate all sale orders are confirmed
        invalid_orders = self.sale_order_ids.filtered(lambda o: o.state not in ['sale', 'done'])
        if invalid_orders:
            raise UserError(_(
                'All sale orders must be confirmed (Sale or Done status).\n\n'
                'Invalid orders:\n%s'
            ) % '\n'.join([f'- {o.name}: {o.state}' for o in invalid_orders]))

        # Prepare commission values
        commission_vals = {
            'user_id': self.user_id.id,
            'role_id': self.role_id.id,
            'commission_type': self.commission_type,
            # No plan_id - manual commissions don't need a plan
            'date': fields.Date.context_today(self),
            'base_amount': 0.0,  # Not used for manual commissions
            'commission_amount': self.manual_amount,  # Store directly
            'is_adjustment': True,  # Mark as manual/adjustment
            'status': 'unpaid',
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
        }

        # Link sale orders
        # If single sale order, use sale_order_id; if multiple, use linked_sale_order_ids
        if len(self.sale_order_ids) == 1:
            commission_vals['sale_order_id'] = self.sale_order_ids[0].id
        else:
            # Use first order as primary, rest as linked
            commission_vals['sale_order_id'] = self.sale_order_ids[0].id
            commission_vals['linked_sale_order_ids'] = [(6, 0, self.sale_order_ids.ids)]

        # Create commission
        commission = self.env['sale.commission'].create(commission_vals)

        # Post message with reason
        commission.message_post(
            body=_('<strong>Manual Commission Created</strong><br/>'
                   'Created by: %s<br/>'
                   'Reason: %s<br/>'
                   'Linked Sale Orders: %s') % (
                self.env.user.name,
                self.description,
                ', '.join(self.sale_order_ids.mapped('name'))
            ),
            subject=_('Manual Commission Created'),
            message_type='comment'
        )

        # Optionally create PO immediately
        if self.create_po_immediately:
            try:
                return commission.action_create_po_from_commissions()
            except Exception as e:
                # If PO creation fails, still show the commission
                raise UserError(_(
                    'Commission created successfully but PO creation failed:\n%s\n\n'
                    'You can create the PO manually from the commission record.'
                ) % str(e))

        # Show success message and open commission
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Manual Commission Created'),
                'message': _('Commission %s for %s (%s) has been created successfully.') % (
                    commission.name,
                    self.user_id.name,
                    '{:,.2f} {}'.format(self.manual_amount, self.currency_id.symbol)
                ),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'sale.commission',
                    'res_id': commission.id,
                    'views': [(False, 'form')],
                    'target': 'current',
                },
            }
        }

    def action_cancel(self):
        """Cancel the wizard"""
        return {'type': 'ir.actions.act_window_close'}
