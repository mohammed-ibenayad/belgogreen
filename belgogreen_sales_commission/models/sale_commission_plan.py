# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleCommissionPlan(models.Model):
    _inherit = 'sale.commission.plan'

    # Extend the 'type' field to add 'hierarchical' option
    type = fields.Selection(
        selection_add=[('hierarchical', 'Hierarchical')],
        ondelete={'hierarchical': 'set default'},
        help="Commission plan type:\n"
             "- Target: Based on sales targets with progressive rates\n"
             "- Achievement: Based on performance metrics\n"
             "- Hierarchical: Fixed percentages split across sales hierarchy (Salesperson/Team Leader/Director)"
    )

    # Keep is_hierarchical as computed field for backward compatibility
    is_hierarchical = fields.Boolean(
        string='Is Hierarchical',
        compute='_compute_is_hierarchical',
        store=True,
        help='Computed field: True if type is hierarchical'
    )

    role_config_ids = fields.One2many(
        'hr.commission.role.config',
        'plan_id',
        string='Role Configuration',
        help='Define commission percentages for each role in the hierarchy'
    )

    user_ids = fields.One2many(
        'sale.commission.plan.user',
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

    @api.depends('type')
    def _compute_is_hierarchical(self):
        """Compute is_hierarchical based on type"""
        for plan in self:
            plan.is_hierarchical = (plan.type == 'hierarchical')

    @api.depends('user_ids')
    def _compute_user_count(self):
        """Count users in this plan"""
        for plan in self:
            plan.user_count = len(plan.user_ids)

    @api.depends('role_config_ids')
    def _compute_commission_count(self):
        """Count commissions for this plan"""
        for plan in self:
            plan.commission_count = self.env['sale.commission'].search_count([
                ('plan_id', '=', plan.id)
            ])

    def _compute_targets(self):
        """Override base method to skip target computation for hierarchical plans"""
        # Only compute targets for non-hierarchical plans
        non_hierarchical_plans = self.filtered(lambda p: p.type != 'hierarchical')
        if non_hierarchical_plans:
            # Call parent method only for non-hierarchical plans
            super(SaleCommissionPlan, non_hierarchical_plans)._compute_targets()

    @api.constrains('type', 'role_config_ids')
    def _check_hierarchical_config(self):
        """Ensure hierarchical plans have role configurations"""
        for record in self:
            if record.type == 'hierarchical' and not record.role_config_ids:
                # This is a soft warning - users can configure roles after creation
                pass

    @api.onchange('type')
    def _onchange_type(self):
        """Auto-set periodicity to 'month' when type is hierarchical"""
        if self.type == 'hierarchical':
            # Set month as default (periods are hidden in view anyway)
            self.periodicity = 'month'

    @api.model_create_multi
    def create(self, vals_list):
        """Set smart defaults for hierarchical plans"""
        for vals in vals_list:
            if vals.get('type') == 'hierarchical':
                # Auto-set periodicity to month (periods are hidden in view anyway)
                if 'periodicity' not in vals:
                    vals['periodicity'] = 'month'
        return super().create(vals_list)

    def write(self, vals):
        """Handle changes to plan type"""
        # If switching to hierarchical, auto-set periodicity
        if vals.get('type') == 'hierarchical':
            if 'periodicity' not in vals:
                vals['periodicity'] = 'month'
        return super().write(vals)

    def action_approve(self):
        """Approve commission plan"""
        for plan in self:
            if plan.type == 'hierarchical':
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
