# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CommissionClaimWizard(models.TransientModel):
    _name = 'commission.claim.wizard'
    _description = 'Commission Claim Wizard'

    commission_ids = fields.Many2many(
        'sale.commission',
        string='Commissions to Claim',
        required=True,
    )
    commission_count = fields.Integer(
        string='Number of Commissions',
        compute='_compute_commission_count',
    )
    total_amount = fields.Float(
        string='Total Commission Amount',
        compute='_compute_total_amount',
        digits='Product Price',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends('commission_ids')
    def _compute_commission_count(self):
        for wizard in self:
            wizard.commission_count = len(wizard.commission_ids)

    @api.depends('commission_ids')
    def _compute_total_amount(self):
        for wizard in self:
            wizard.total_amount = sum(wizard.commission_ids.mapped('commission_amount'))

    @api.model
    def default_get(self, fields_list):
        res = super(CommissionClaimWizard, self).default_get(fields_list)

        # Get selected commission IDs from context
        commission_ids = self.env.context.get('active_ids', [])

        if not commission_ids:
            raise UserError(_('Please select at least one commission to claim.'))

        commissions = self.env['sale.commission'].browse(commission_ids)

        # Validate commissions
        invalid_commissions = commissions.filtered(
            lambda c: c.payment_status != 'unpaid' or c.state != 'confirmed'
        )

        if invalid_commissions:
            raise UserError(_(
                'Only unpaid and confirmed commissions can be claimed.\n'
                'Please remove the following commissions:\n%s'
            ) % '\n'.join(invalid_commissions.mapped('name')))

        # Check if user is claiming their own commissions
        user_commissions = commissions.filtered(lambda c: c.user_id.id != self.env.uid)
        if user_commissions and not self.env.user.has_group('belgogreen_sales_commission.group_commission_manager'):
            raise UserError(_('You can only claim your own commissions.'))

        res['commission_ids'] = [(6, 0, commission_ids)]

        return res

    def action_confirm_claim(self):
        """Create the claim for selected commissions"""
        self.ensure_one()

        if not self.commission_ids:
            raise UserError(_('No commissions selected.'))

        # Create the claim
        claim = self.env['sale.commission.claim'].create({
            'user_id': self.env.uid,
            'commission_ids': [(6, 0, self.commission_ids.ids)],
        })

        # Update commission payment status to 'claimed'
        self.commission_ids.write({'payment_status': 'claimed'})

        # Notify admins
        claim._notify_admins()

        # Return action to view the created claim
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Claim Submitted'),
                'message': _('Your claim %s for %s commissions totaling %s has been submitted successfully.') % (
                    claim.name,
                    len(self.commission_ids),
                    '{:,.2f} {}'.format(self.total_amount, self.currency_id.symbol)
                ),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'sale.commission.claim',
                    'res_id': claim.id,
                    'views': [(False, 'form')],
                    'target': 'current',
                },
            }
        }

    def action_cancel(self):
        """Cancel the wizard"""
        return {'type': 'ir.actions.act_window_close'}
