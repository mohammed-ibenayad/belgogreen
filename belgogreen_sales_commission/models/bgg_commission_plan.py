# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BggCommissionPlan(models.Model):
    """Hierarchical commission plan.

    Owned by this module so that it no longer depends on the Enterprise
    ``sale_commission`` module (``sale.commission.plan``). Existing plans are
    copied over with their ids by the 19.0.1.0.0 migration.
    """
    _name = 'bgg.commission.plan'
    _description = 'Hierarchical Commission Plan'
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(string='Name', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    date_from = fields.Date(
        string='Start Date',
        tracking=True,
        help='First day the plan applies (invoice date). Leave empty for no start limit.'
    )
    date_to = fields.Date(
        string='End Date',
        tracking=True,
        help='Last day the plan applies (invoice date). Leave empty for no end limit.'
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )

    role_config_ids = fields.One2many(
        'hr.commission.role.config',
        'plan_id',
        string='Role Configuration',
        help='Define commission percentages for each role in the hierarchy'
    )

    user_ids = fields.One2many(
        'bgg.commission.plan.user',
        'plan_id',
        string='Assigned Users',
        help='Users who participate in this commission plan with their roles and hierarchy'
    )

    user_count = fields.Integer(
        string='User Count',
        compute='_compute_user_count',
        help='Number of users assigned to this plan'
    )

    require_invoice_paid = fields.Boolean(
        string='Require Paid Invoice',
        default=True,
        help='Only calculate commissions when the invoice is fully paid'
    )

    commission_count = fields.Integer(
        string='Commission Count',
        compute='_compute_commission_count'
    )

    @api.depends('user_ids')
    def _compute_user_count(self):
        """Count users in this plan"""
        for plan in self:
            plan.user_count = len(plan.user_ids)

    def _compute_commission_count(self):
        """Count commissions for this plan"""
        for plan in self:
            plan.commission_count = self.env['sale.commission'].search_count([
                ('plan_id', '=', plan.id)
            ])

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for plan in self:
            if plan.date_from and plan.date_to and plan.date_from > plan.date_to:
                raise ValidationError(_('The end date of plan %s must be after its start date.') % plan.name)

    def action_approve(self):
        """Approve commission plan"""
        for plan in self:
            if not plan.role_config_ids:
                raise ValidationError(_(
                    'Cannot approve hierarchical plan without role configurations. '
                    'Please add role percentages in the "Role Percentages" tab.'
                ))
            if not plan.user_ids:
                raise ValidationError(_(
                    'Cannot approve hierarchical plan without users. '
                    'Please add users in the "Users & Hierarchy" tab.'
                ))
            # Check that there's at least one top-level user
            top_level_users = plan.user_ids.filtered(lambda u: not u.manager_id)
            if not top_level_users:
                raise ValidationError(_(
                    'Hierarchical plan must have at least one top-level user '
                    '(user without a manager). Please review the hierarchy.'
                ))
            plan.state = 'approved'
        return True

    def action_draft(self):
        """Reset commission plan to draft"""
        self.write({'state': 'draft'})
        return True

    def action_cancel(self):
        """Cancel commission plan: it no longer generates commissions"""
        self.write({'state': 'cancel'})
        return True

    def action_view_commissions(self):
        """View all commissions for this plan"""
        self.ensure_one()
        return {
            'name': _('Commissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.commission',
            'view_mode': 'list,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {
                'default_plan_id': self.id,
                'search_default_group_by_role': 1,
            }
        }
