# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    # DYNAMIC ROLE SYSTEM
    commission_role_id = fields.Many2one(
        'sale.commission.role',
        string='Commission Role',
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help='The role of this user in the commission hierarchy'
    )

    commission_role_sequence = fields.Integer(
        string='Role Level',
        related='commission_role_id.sequence',
        store=True,
        readonly=True,
        help='Hierarchy level from role (lower number = lower in hierarchy)'
    )

    # UNIFIED HIERARCHY FIELD (replaces team_leader_id and sales_director_id)
    commission_manager_id = fields.Many2one(
        'res.users',
        string='Commission Manager',
        domain="[('commission_role_id', '!=', False), ('id', '!=', id), ('company_id', '=', company_id)]",
        help='Direct manager in the commission hierarchy'
    )

    # REVERSE RELATION (replaces team_member_ids and director_team_ids)
    commission_subordinate_ids = fields.One2many(
        'res.users',
        'commission_manager_id',
        string='Direct Subordinates',
        help='Users who report directly to this user in commission hierarchy'
    )

    my_commission_ids = fields.One2many(
        'sale.commission',
        'user_id',
        string='My Commissions'
    )

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

    team_commission_count = fields.Integer(
        string='Team Commission Count',
        compute='_compute_team_commission_stats',
        help='Total commissions for all subordinates'
    )

    team_unpaid_total = fields.Monetary(
        string='Team Unpaid Commissions',
        compute='_compute_team_commission_stats',
        currency_field='company_currency_id',
        help='Total unpaid commissions for all subordinates'
    )

    active_commission_count = fields.Integer(
        string='Active Commissions',
        compute='_compute_active_commissions',
        help='Number of unpaid or claimed commissions'
    )

    has_subordinates = fields.Boolean(
        string='Has Subordinates',
        compute='_compute_has_subordinates',
        help='True if user has team members reporting to them'
    )

    subordinate_count = fields.Integer(
        string='Number of Subordinates',
        compute='_compute_has_subordinates',
        help='Total number of subordinates (direct and indirect)'
    )

    hierarchy_warnings = fields.Text(
        string='Hierarchy Warnings',
        compute='_compute_hierarchy_warnings',
        help='Warnings about hierarchy structure issues'
    )

    has_hierarchy_anomaly = fields.Boolean(
        string='Has Hierarchy Anomaly',
        compute='_compute_hierarchy_anomalies',
        store=True,
        search='_search_has_hierarchy_anomaly',
        help='True if user has hierarchical assignment issues that need review'
    )

    anomaly_type = fields.Selection([
        ('missing_manager', 'Missing Required Manager'),
        ('top_role_has_manager', 'Top-level role should not have manager'),
        ('no_role_with_manager', 'Manager assigned without commission role'),
        ('manager_lower_level', 'Manager has lower hierarchy level than subordinate'),
        ('circular_hierarchy', 'Circular reference in hierarchy'),
    ], string='Anomaly Type', compute='_compute_hierarchy_anomalies', store=True)

    anomaly_description = fields.Text(
        string='Description de l\'anomalie',
        compute='_compute_hierarchy_anomalies',
        store=True,
        help='Description détaillée de l\'anomalie hiérarchique'
    )

    has_active_commission_plan = fields.Boolean(
        string='Has Active Commission Plan',
        compute='_compute_has_active_commission_plan',
        help='True if user is in an active hierarchical commission plan'
    )

    @api.depends('commission_role_id')
    def _compute_has_active_commission_plan(self):
        """Check if user is in an active commission plan"""
        for user in self:
            if not user.commission_role_id:
                user.has_active_commission_plan = False
            else:
                # Check if there's an active hierarchical plan
                active_plans = self.env['sale.commission.plan'].search([
                    ('is_hierarchical', '=', True),
                    ('state', '=', 'approved'),
                ], limit=1)
                user.has_active_commission_plan = bool(active_plans)

    @api.depends('my_commission_ids', 'my_commission_ids.payment_status', 'my_commission_ids.commission_amount')
    def _compute_commission_stats(self):
        """Compute commission statistics for the user"""
        for user in self:
            commissions = user.my_commission_ids
            user.commission_count = len(commissions)
            user.commission_unpaid_total = sum(
                commissions.filtered(lambda c: c.payment_status == 'unpaid').mapped('commission_amount')
            )
            user.commission_paid_total = sum(
                commissions.filtered(lambda c: c.payment_status == 'paid').mapped('commission_amount')
            )

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

    def _get_all_subordinate_ids(self):
        """
        Get all subordinate user IDs recursively.

        This method traverses the hierarchy tree downwards to find all users
        who report to this user, directly or indirectly through the unified
        commission_manager_id field.

        Returns:
            list: List of unique user IDs for all active subordinates (no duplicates)
        """
        self.ensure_one()
        subordinate_ids = set()  # Use set to avoid duplicates

        # Get direct reports - SIMPLIFIED with unified field
        direct_reports = self.commission_subordinate_ids.filtered(lambda u: u.active)

        # Add direct reports to the set
        subordinate_ids.update(direct_reports.ids)

        # Recursively get subordinates of direct reports
        for subordinate in direct_reports:
            subordinate_ids.update(subordinate._get_all_subordinate_ids())

        return list(subordinate_ids)  # Convert back to list for compatibility

    def _compute_team_commission_stats(self):
        """Compute commission statistics for all subordinates"""
        for user in self:
            subordinate_ids = user._get_all_subordinate_ids()

            if not subordinate_ids:
                user.team_commission_count = 0
                user.team_unpaid_total = 0.0
            else:
                # Get all commissions for subordinates
                team_commissions = self.env['sale.commission'].search([
                    ('user_id', 'in', subordinate_ids)
                ])

                user.team_commission_count = len(team_commissions)
                user.team_unpaid_total = sum(
                    team_commissions.filtered(lambda c: c.payment_status == 'unpaid').mapped('commission_amount')
                )

    def action_view_team_commissions(self):
        """Open commissions for all subordinates"""
        self.ensure_one()
        subordinate_ids = self._get_all_subordinate_ids()

        return {
            'name': _('Commissions de l\'équipe'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.commission',
            'view_mode': 'list,form',
            'domain': [('user_id', 'in', subordinate_ids)],
            'context': {
                'search_default_group_by_user': 1,
            }
        }

    @api.depends('my_commission_ids', 'my_commission_ids.payment_status')
    def _compute_active_commissions(self):
        """Compute count of active (unpaid/claimed) commissions"""
        for user in self:
            active_commissions = user.my_commission_ids.filtered(
                lambda c: c.payment_status in ['unpaid', 'claimed', 'processing']
            )
            user.active_commission_count = len(active_commissions)

    @api.depends('commission_subordinate_ids')
    def _compute_has_subordinates(self):
        """Check if user has any subordinates"""
        for user in self:
            subordinate_ids = user._get_all_subordinate_ids()
            user.has_subordinates = bool(subordinate_ids)
            user.subordinate_count = len(subordinate_ids)

    @api.depends('commission_role_id', 'commission_manager_id', 'commission_subordinate_ids')
    def _compute_hierarchy_warnings(self):
        """Generate warnings about hierarchy issues using dynamic role configuration"""
        for user in self:
            warnings = []

            if user.commission_role_id:
                role = user.commission_role_id

                # Check if role can have subordinates but doesn't have role configured for it
                if user.commission_subordinate_ids and not role.can_manage_subordinates:
                    warnings.append(_("Warning: Role '%s' should not have subordinates, but %d users report to this user") % (
                        role.name, len(user.commission_subordinate_ids)))

                # Check if user has manager but role doesn't require one
                if user.commission_manager_id and not role.requires_manager:
                    warnings.append(_("Warning: Role '%s' doesn't require a manager, but has one assigned") % role.name)

                # Check if user needs manager but doesn't have one
                if not user.commission_manager_id and role.requires_manager:
                    warnings.append(_("Warning: Role '%s' requires a manager, but none is assigned") % role.name)

            user.hierarchy_warnings = '\n'.join(warnings) if warnings else ''

    @api.depends('commission_role_id', 'commission_manager_id',
                 'commission_manager_id.commission_role_id')
    def _compute_hierarchy_anomalies(self):
        """Detect hierarchy anomalies using dynamic role configuration"""
        for user in self:
            anomaly = False
            anomaly_type = False
            description = ''

            if user.commission_role_id:
                role = user.commission_role_id

                # ANOMALY 1: Role requires manager but none assigned
                if role.requires_manager and not user.commission_manager_id:
                    anomaly = True
                    anomaly_type = 'missing_manager'
                    description = _("User with role '%s' requires a manager but none is assigned. "
                                  "Please assign a manager in the commission hierarchy.") % role.name

                # ANOMALY 2: Role shouldn't have manager (top-level)
                elif not role.requires_manager and user.commission_manager_id:
                    anomaly = True
                    anomaly_type = 'top_role_has_manager'
                    description = _("User with role '%s' is a top-level role and should not have a manager. "
                                  "Current manager: %s") % (role.name, user.commission_manager_id.name)

                # ANOMALY 3: Manager has lower hierarchy level (sequence) than subordinate
                elif user.commission_manager_id and user.commission_manager_id.commission_role_id:
                    manager_level = user.commission_manager_id.commission_role_id.sequence
                    user_level = role.sequence

                    if manager_level <= user_level:
                        anomaly = True
                        anomaly_type = 'manager_lower_level'
                        description = _("Hierarchy issue: Manager '%s' (level %d - %s) has same or lower hierarchy level "
                                      "than subordinate '%s' (level %d - %s). Manager should have higher level.") % (
                                          user.commission_manager_id.name, manager_level,
                                          user.commission_manager_id.commission_role_id.name,
                                          user.name, user_level, role.name
                                      )

            # ANOMALY 4: Manager assigned but no role
            elif not user.commission_role_id and user.commission_manager_id:
                anomaly = True
                anomaly_type = 'no_role_with_manager'
                description = _("User has manager '%s' assigned but no commission role defined. "
                              "Please assign a commission role first.") % user.commission_manager_id.name

            # ANOMALY 5: Detect circular hierarchy
            if user.commission_manager_id and not anomaly:
                if user._has_circular_hierarchy():
                    anomaly = True
                    anomaly_type = 'circular_hierarchy'
                    description = _("Circular reference detected in commission hierarchy. "
                                  "User is in their own management chain.")

            user.has_hierarchy_anomaly = anomaly
            user.anomaly_type = anomaly_type
            user.anomaly_description = description

    def _has_circular_hierarchy(self):
        """Check if user's hierarchy contains a circular reference"""
        self.ensure_one()
        visited = set()
        current = self

        while current.commission_manager_id:
            if current.id in visited:
                return True  # Circular reference found
            visited.add(current.id)
            current = current.commission_manager_id

            if len(visited) > 50:  # Safety limit
                return True

        return False

    def _search_has_hierarchy_anomaly(self, operator, value):
        """Search method for has_hierarchy_anomaly field"""
        # Trigger recomputation for all users with roles or managers
        users = self.search([
            '|',
            ('commission_role_id', '!=', False),
            ('commission_manager_id', '!=', False)
        ])

        # Get users with anomalies after computation
        if operator == '=' and value:
            return [('id', 'in', users.filtered('has_hierarchy_anomaly').ids)]
        elif operator == '=' and not value:
            return [('id', 'in', users.filtered(lambda u: not u.has_hierarchy_anomaly).ids)]

        return []

    def write(self, vals):
        """Override write to validate role changes with dynamic roles"""
        # Check if commission_role_id is being changed
        if 'commission_role_id' in vals:
            for user in self:
                old_role_id = user.commission_role_id
                new_role_id = self.env['sale.commission.role'].browse(vals['commission_role_id']) if vals['commission_role_id'] else False

                # Skip if role is not actually changing
                if old_role_id == new_role_id:
                    continue

                # Build warning message
                warnings = []
                blocking_issues = []

                old_role_name = old_role_id.name if old_role_id else _('None')
                new_role_name = new_role_id.name if new_role_id else _('None')

                # Check for active commissions
                if user.active_commission_count > 0:
                    warnings.append(
                        _("• User has %s active commission(s) with role '%s'") % (
                            user.active_commission_count,
                            old_role_name
                        )
                    )

                # Check for subordinates - if changing to role that can't have subordinates
                if user.has_subordinates and new_role_id and not new_role_id.can_manage_subordinates:
                    subordinate_count = user.subordinate_count
                    blocking_issues.append(
                        _("• Cannot change to role '%s': User has %s subordinate(s) who will be orphaned. "
                          "Role '%s' cannot manage subordinates.") % (
                            new_role_name, subordinate_count, new_role_name
                        )
                    )

                # Warn if user manages subordinates
                elif user.has_subordinates:
                    warnings.append(
                        _("• User manages %s subordinate(s) in the hierarchy") % user.subordinate_count
                    )

                # If there are blocking issues, prevent the change
                if blocking_issues:
                    raise UserError(
                        _("Cannot change commission role from '%s' to '%s' for user %s:\n\n%s\n\nPlease reassign subordinates first.") % (
                            old_role_name,
                            new_role_name,
                            user.name,
                            '\n'.join(blocking_issues)
                        )
                    )

                # If there are warnings (but not blocking), log them
                if warnings:
                    message = _("Commission role changed from '%s' to '%s':\n\n%s\n\nPlease ensure commission plans are updated accordingly.") % (
                        old_role_name,
                        new_role_name,
                        '\n'.join(warnings)
                    )
                    # Post message to user's chatter
                    user.message_post(body=message, subject=_("Commission role modified"))

        return super(ResUsers, self).write(vals)
