# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Commission records
    my_commission_ids = fields.One2many(
        'sale.commission',
        'user_id',
        string='My Commissions'
    )

    # Commission plan assignments (NEW - replaces global role)
    commission_plan_assignments = fields.One2many(
        'sale.commission.plan.user',
        'user_id',
        string='Commission Plan Assignments',
        help='Shows which commission plans this user is assigned to and their role in each'
    )

    # Commission statistics
    commission_count = fields.Integer(
        string='Commission Count',
        compute='_compute_commission_stats',
        store=True
    )

    commission_unpaid_total = fields.Monetary(
        string='Unpaid Commissions',
        compute='_compute_commission_stats',
        store=True,
        currency_field='company_currency_id'
    )

    commission_paid_total = fields.Monetary(
        string='Paid Commissions',
        compute='_compute_commission_stats',
        store=True,
        currency_field='company_currency_id'
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        related='company_id.currency_id',
        readonly=True
    )

    active_commission_count = fields.Integer(
        string='Active Commissions',
        compute='_compute_active_commissions',
        help='Number of unpaid or claimed commissions'
    )

    @api.depends('my_commission_ids', 'my_commission_ids.status', 'my_commission_ids.commission_amount')
    def _compute_commission_stats(self):
        """Compute commission statistics for the user"""
        for user in self:
            commissions = user.my_commission_ids
            user.commission_count = len(commissions)
            user.commission_unpaid_total = sum(
                commissions.filtered(lambda c: c.status == 'unpaid').mapped('commission_amount')
            )
            user.commission_paid_total = sum(
                commissions.filtered(lambda c: c.status == 'paid').mapped('commission_amount')
            )

    @api.depends('my_commission_ids', 'my_commission_ids.status')
    def _compute_active_commissions(self):
        """Compute count of active (unpaid/claimed) commissions"""
        for user in self:
            active_commissions = user.my_commission_ids.filtered(
                lambda c: c.status in ['unpaid', 'claimed', 'processing']
            )
            user.active_commission_count = len(active_commissions)

    def action_view_my_commissions(self):
        """Open the user's commissions"""
        self.ensure_one()
        return {
            'name': _('Mes commissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.commission',
            'view_mode': 'list,form',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id}
        }

    def action_view_commissions(self):
        """Open the user's commissions (alias for action_view_my_commissions)"""
        return self.action_view_my_commissions()

    def action_view_commission_plans(self):
        """View commission plans this user is assigned to"""
        self.ensure_one()
        return {
            'name': _('My Commission Plans'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.commission.plan',
            'view_mode': 'list,form',
            'domain': [('user_ids.user_id', '=', self.id)],
        }
