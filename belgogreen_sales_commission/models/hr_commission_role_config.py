# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrCommissionRoleConfig(models.Model):
    _name = 'hr.commission.role.config'
    _description = 'Commission Configuration by Role'
    _order = 'plan_id, role_id'

    plan_id = fields.Many2one(
        'sale.commission.plan',
        string='Commission Plan',
        required=True,
        ondelete='cascade',
        help='The commission plan this configuration applies to'
    )

    role_id = fields.Many2one(
        'sale.commission.role',
        string='Role',
        required=True,
        domain="[('company_id', '=', company_id)]",
        help='The role this percentage applies to'
    )

    # DUAL PERCENTAGE APPROACH
    # This solves the problem: "What % when Team Leader makes their OWN sale vs manages a sale?"
    direct_sale_percentage = fields.Float(
        string='Direct Sale %',
        required=True,
        digits=(5, 2),
        default=0.0,
        help='Commission percentage when user with this role makes their own sale (e.g., Team Leader selling directly = 5%)'
    )

    override_percentage = fields.Float(
        string='Override %',
        required=True,
        digits=(5, 2),
        default=0.0,
        help='Commission percentage when user receives commission on subordinate\'s sale (e.g., Team Leader getting commission on salesperson\'s sale = 2%)'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='plan_id.company_id',
        store=True,
        readonly=True
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.constrains('plan_id', 'role_id')
    def _check_unique_plan_role(self):
        """Ensure only one configuration per role per plan"""
        for record in self:
            if record.plan_id and record.role_id:
                duplicate = self.search([
                    ('plan_id', '=', record.plan_id.id),
                    ('role_id', '=', record.role_id.id),
                    ('id', '!=', record.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_('Only one percentage configuration per role per plan is allowed!'))

    @api.constrains('direct_sale_percentage', 'override_percentage')
    def _check_percentages(self):
        """Validate that percentages are between 0 and 100"""
        for record in self:
            if record.direct_sale_percentage < 0 or record.direct_sale_percentage > 100:
                raise ValidationError(
                    _('Direct sale percentage must be between 0 and 100. Got: %s') % record.direct_sale_percentage
                )
            if record.override_percentage < 0 or record.override_percentage > 100:
                raise ValidationError(
                    _('Override percentage must be between 0 and 100. Got: %s') % record.override_percentage
                )

    def _compute_display_name(self):
        """Custom display name for Odoo 18"""
        for record in self:
            record.display_name = _('%(plan)s - %(role)s (Direct: %(direct)s%% / Override: %(override)s%%)') % {
                'plan': record.plan_id.name,
                'role': record.role_id.name,
                'direct': record.direct_sale_percentage,
                'override': record.override_percentage
            }
