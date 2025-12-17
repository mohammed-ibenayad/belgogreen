# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleCommissionPlanUser(models.Model):
    _name = 'sale.commission.plan.user'
    _description = 'Commission Plan User Assignment'
    _order = 'plan_id, role_sequence desc, user_id'

    # Core fields
    plan_id = fields.Many2one(
        'sale.commission.plan',
        string='Commission Plan',
        required=True,
        ondelete='cascade',
        index=True
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True
    )

    role_id = fields.Many2one(
        'sale.commission.role',
        string='Role',
        required=True,
        domain="[('company_id', '=', company_id)]",
        help='The role of this user in this commission plan'
    )

    manager_id = fields.Many2one(
        'res.users',
        string='Manager (in this plan)',
        help='Direct manager in THIS commission plan\'s hierarchy'
    )

    # Related/Computed fields
    company_id = fields.Many2one(
        'res.company',
        related='plan_id.company_id',
        store=True,
        readonly=True
    )

    role_sequence = fields.Integer(
        related='role_id.sequence',
        store=True,
        readonly=True,
        help='Hierarchy level (higher = higher in hierarchy)'
    )

    role_name = fields.Char(
        related='role_id.name',
        string='Role Name',
        readonly=True
    )

    # SQL constraints
    _sql_constraints = [
        ('unique_user_plan', 'unique(plan_id, user_id)',
         'A user can only be assigned once per commission plan!')
    ]

    @api.constrains('manager_id', 'user_id')
    def _check_no_self_management(self):
        """User cannot be their own manager"""
        for rec in self:
            if rec.manager_id and rec.manager_id.id == rec.user_id.id:
                raise ValidationError(_('A user cannot be their own manager!'))

    @api.constrains('manager_id', 'role_id')
    def _check_manager_hierarchy(self):
        """Manager must have higher hierarchy level (higher sequence)"""
        for rec in self:
            if rec.manager_id:
                # Find manager's role in same plan
                manager_plan_user = self.search([
                    ('plan_id', '=', rec.plan_id.id),
                    ('user_id', '=', rec.manager_id.id)
                ], limit=1)

                if not manager_plan_user:
                    raise ValidationError(_(
                        'Manager %s must be assigned to the same commission plan first.'
                    ) % rec.manager_id.name)

                if manager_plan_user.role_id:
                    if manager_plan_user.role_sequence <= rec.role_sequence:
                        raise ValidationError(_(
                            'Manager %s (level %d - %s) must have higher hierarchy level '
                            'than subordinate %s (level %d - %s).'
                        ) % (
                            rec.manager_id.name, manager_plan_user.role_sequence,
                            manager_plan_user.role_id.name,
                            rec.user_id.name, rec.role_sequence, rec.role_id.name
                        ))

    @api.constrains('plan_id', 'user_id', 'manager_id')
    def _check_circular_hierarchy(self):
        """Prevent circular references in hierarchy"""
        for rec in self:
            if not rec.manager_id:
                continue

            visited = set()
            current = rec

            while current and current.manager_id:
                if current.id in visited:
                    raise ValidationError(_(
                        'Circular hierarchy detected! User %s is in their own management chain.'
                    ) % rec.user_id.name)

                visited.add(current.id)

                # Find manager's record in same plan
                current = self.search([
                    ('plan_id', '=', rec.plan_id.id),
                    ('user_id', '=', current.manager_id.id)
                ], limit=1)

                # Safety limit
                if len(visited) > 50:
                    raise ValidationError(_('Hierarchy depth exceeds 50 levels. Possible circular reference.'))

    def name_get(self):
        """Custom display name"""
        result = []
        for rec in self:
            name = '%s - %s (%s)' % (
                rec.plan_id.name or 'Plan',
                rec.user_id.name or 'User',
                rec.role_id.name or 'Role'
            )
            result.append((rec.id, name))
        return result

    @api.model
    def _get_user_role_in_plan(self, user_id, plan_id):
        """
        Helper method to quickly get user's role in a specific plan

        Args:
            user_id: ID of the user
            plan_id: ID of the commission plan

        Returns:
            sale.commission.plan.user record or empty recordset
        """
        return self.search([
            ('user_id', '=', user_id),
            ('plan_id', '=', plan_id)
        ], limit=1)

    def _get_hierarchy_chain(self):
        """
        Get the full management chain upwards from this user

        Returns:
            List of sale.commission.plan.user records from bottom to top
        """
        self.ensure_one()
        chain = [self]
        current = self
        seen_ids = set([self.id])

        while current.manager_id:
            manager_record = self.search([
                ('plan_id', '=', self.plan_id.id),
                ('user_id', '=', current.manager_id.id)
            ], limit=1)

            if not manager_record or manager_record.id in seen_ids:
                break

            chain.append(manager_record)
            seen_ids.add(manager_record.id)
            current = manager_record

            # Safety check
            if len(chain) > 50:
                break

        return chain
