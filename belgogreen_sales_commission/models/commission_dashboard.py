# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class CommissionDashboard(models.TransientModel):
    _name = 'commission.dashboard'
    _description = 'Commission Dashboard'

    @api.model
    def get_dashboard_data(self):
        """Get all dashboard data for the current user

        Note: Menu visibility is controlled by ir.ui.menu override.
        Users without plan assignments won't see the dashboard menu.
        """
        user = self.env.user

        # Get date ranges
        today = fields.Date.today()
        first_day_month = today.replace(day=1)
        last_month = first_day_month - timedelta(days=1)
        first_day_last_month = last_month.replace(day=1)
        six_months_ago = today - relativedelta(months=6)

        # Get user's commissions
        my_commissions = self.env['sale.commission'].search([
            ('user_id', '=', user.id)
        ])

        # Get team commissions (if user is a manager in any plan)
        # In plan-based architecture, find users that report to this user in any plan
        subordinate_assignments = self.env['sale.commission.plan.user'].search([
            ('manager_id', '=', user.id)
        ])
        subordinate_user_ids = subordinate_assignments.mapped('user_id').ids

        team_commissions = self.env['sale.commission'].search([
            ('user_id', 'in', subordinate_user_ids)
        ])

        # Check if user manages a team
        has_team = len(subordinate_user_ids) > 0

        # Check if user is in active commission plan
        has_active_plan = self._user_has_active_commission_plan(user)

        # Calculate KPIs
        kpis = self._compute_kpis(my_commissions, team_commissions, first_day_month, today)

        # Get chart data
        chart_data = self._compute_chart_data(user, six_months_ago, today)

        # Get company currency
        company = user.company_id
        currency_info = {
            'id': company.currency_id.id,
            'name': company.currency_id.name,
            'symbol': company.currency_id.symbol,
            'position': company.currency_id.position,  # 'before' or 'after'
            'decimal_places': company.currency_id.decimal_places,
        }

        # Get user's primary plan assignment (first active one)
        user_assignment = self.env['sale.commission.plan.user'].search([
            ('user_id', '=', user.id),
            ('plan_id.state', '=', 'approved')
        ], limit=1)

        return {
            'kpis': kpis,
            'charts': chart_data,
            'currency': currency_info,
            'user_info': {
                'name': user.name,
                'role': user_assignment.role_id.name if user_assignment else 'No Role',
                'manager': user_assignment.manager_id.name if user_assignment and user_assignment.manager_id else None,
                'has_team': has_team,
                'has_active_plan': has_active_plan,
            }
        }

    def _user_has_active_commission_plan(self, user):
        """Check if user is assigned to an active commission plan"""
        # Check if user has any plan assignments in approved plans
        user_assignments = self.env['sale.commission.plan.user'].search([
            ('user_id', '=', user.id),
            ('plan_id.state', '=', 'approved'),
        ], limit=1)

        return bool(user_assignments)

    def _compute_kpis(self, my_commissions, team_commissions, first_day_month, today):
        """Compute KPI metrics"""
        # My Commissions
        my_total = sum(my_commissions.mapped('commission_amount'))
        my_pending = sum(my_commissions.filtered(lambda c: c.status == 'unpaid').mapped('commission_amount'))
        my_paid = sum(my_commissions.filtered(lambda c: c.status == 'paid').mapped('commission_amount'))

        # This Month
        my_month_comms = my_commissions.filtered(lambda c: c.date >= first_day_month)
        my_month_total = sum(my_month_comms.mapped('commission_amount'))

        # Get current month name
        import locale
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        except:
            pass
        current_month_name = today.strftime('%B')  # Full month name

        # Team metrics
        team_total = sum(team_commissions.mapped('commission_amount'))
        team_pending = sum(team_commissions.filtered(lambda c: c.status == 'unpaid').mapped('commission_amount'))
        team_members_count = len(set(team_commissions.mapped('user_id')))

        # Pending actions (claims to approve from subordinates in any plan)
        # Get subordinate user IDs from plan assignments
        subordinate_assignments = self.env['sale.commission.plan.user'].search([
            ('manager_id', '=', self.env.user.id)
        ])
        subordinate_user_ids = subordinate_assignments.mapped('user_id').ids

        pending_claims = self.env['sale.commission.claim'].search_count([
            ('state', '=', 'pending'),
            ('user_id', 'in', subordinate_user_ids)
        ])

        return {
            'my_total': my_total,
            'my_pending': my_pending,
            'my_paid': my_paid,
            'my_count': len(my_commissions),
            'my_month_total': my_month_total,
            'my_month_count': len(my_month_comms),
            'current_month_name': current_month_name,
            'team_total': team_total,
            'team_pending': team_pending,
            'team_members': team_members_count,
            'pending_claims': pending_claims,
            'hierarchy_issues': 0,  # Removed - not applicable in plan-based architecture
        }

    def _compute_chart_data(self, user, start_date, end_date):
        """Compute data for charts"""
        # Monthly trend for last 6 months
        monthly_data = []
        current_date = start_date.replace(day=1)

        while current_date <= end_date:
            next_month = current_date + relativedelta(months=1)

            month_commissions = self.env['sale.commission'].search([
                ('user_id', '=', user.id),
                ('date', '>=', current_date),
                ('date', '<', next_month)
            ])

            monthly_data.append({
                'month': current_date.strftime('%b %Y'),
                'amount': sum(month_commissions.mapped('commission_amount')),
                'count': len(month_commissions)
            })

            current_date = next_month

        # Commission by payment status (for histogram)
        my_commissions = self.env['sale.commission'].search([
            ('user_id', '=', user.id)
        ])

        # Get status field to access translations
        status_field = self.env['sale.commission']._fields['status']

        # Build state distribution with amounts and translated labels
        state_distribution = {
            'pending': {
                'amount': sum(my_commissions.filtered(lambda c: c.status == 'unpaid').mapped('commission_amount')),
                'label': dict(status_field.selection).get('unpaid', 'Pending')
            },
            'approved': {
                'amount': sum(my_commissions.filtered(lambda c: c.status == 'claimed').mapped('commission_amount')),
                'label': dict(status_field.selection).get('claimed', 'Approved')
            },
            'paid': {
                'amount': sum(my_commissions.filtered(lambda c: c.status == 'paid').mapped('commission_amount')),
                'label': dict(status_field.selection).get('paid', 'Paid')
            },
            'cancelled': {
                'amount': sum(my_commissions.filtered(lambda c: c.status == 'cancelled').mapped('commission_amount')),
                'label': dict(status_field.selection).get('cancelled', 'Cancelled')
            },
        }

        return {
            'monthly_trend': monthly_data,
            'state_distribution': state_distribution,
        }

    def _get_all_subordinates(self, user, commission_plan):
        """
        Recursively get ALL subordinates in the hierarchy tree for a user within a plan.

        This traverses the entire tree downward, not just direct reports.

        Args:
            user: res.users record (the manager)
            commission_plan: sale.commission.plan record

        Returns:
            recordset of res.users (all subordinates at any level)
        """
        all_subordinate_ids = set()
        users_to_process = [user.id]
        seen_ids = set()  # Prevent circular references

        while users_to_process:
            current_user_id = users_to_process.pop(0)

            if current_user_id in seen_ids:
                continue  # Skip if already processed
            seen_ids.add(current_user_id)

            # Find direct subordinates of current user in this plan
            subordinate_assignments = self.env['sale.commission.plan.user'].search([
                ('manager_id', '=', current_user_id),
                ('plan_id', '=', commission_plan.id)
            ])

            for assignment in subordinate_assignments:
                subordinate_id = assignment.user_id.id
                if subordinate_id not in all_subordinate_ids and subordinate_id != user.id:
                    all_subordinate_ids.add(subordinate_id)
                    users_to_process.append(subordinate_id)  # Add to queue for recursive processing

        return self.env['res.users'].browse(list(all_subordinate_ids))

    @api.model
    def generate_my_commissions(self):
        """Generate commissions for the current user from unprocessed sales orders

        NEW BEHAVIOR: Each user generates ONLY their own commissions:
        - Direct commissions from their own orders
        - Override commissions from all subordinates' orders

        No automatic cascade upward - each person responsible for generating their own.

        Only generates commissions for orders with paid invoices
        Returns count and total amount of generated commissions
        """
        user = self.env.user

        # Check if user has commission plan assignments (removed limit=1)
        user_assignments = self.env['sale.commission.plan.user'].search([
            ('user_id', '=', user.id),
            ('plan_id.state', '=', 'approved'),
            ('plan_id.type', '=', 'hierarchical'),
        ])

        if not user_assignments:
            return {
                'count': 0,
                'total_amount': 0,
                'claimable_amount': 0,
                'success': False,
                'message': 'You are not assigned to any approved hierarchical commission plan'
            }

        SaleOrder = self.env['sale.order']
        Invoice = self.env['account.move']

        total_commissions_created = 0
        total_amount = 0
        plans_processed = []

        # Process each commission plan the user is assigned to
        for user_assignment in user_assignments:
            commission_plan = user_assignment.plan_id
            user_role = user_assignment.role_id

            # Get role configuration for current user
            role_config = self.env['hr.commission.role.config'].search([
                ('plan_id', '=', commission_plan.id),
                ('role_id', '=', user_role.id),
                ('active', '=', True)
            ], limit=1)

            if not role_config:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f'No active configuration found for role {user_role.name} in plan {commission_plan.name}, skipping')
                continue

            commissions_created = 0

            # 1. DIRECT COMMISSIONS: Process user's own orders
            direct_orders = self._get_eligible_orders_for_user(user, Invoice, SaleOrder)
            for order in direct_orders:
                created = self._create_commission_for_user(
                    user=user,
                    role=user_role,
                    commission_type='direct',
                    order=order,
                    commission_plan=commission_plan,
                    role_config=role_config
                )
                commissions_created += created

            # 2. OVERRIDE COMMISSIONS: Process subordinates' orders (within this plan)
            # Get ALL subordinates in the hierarchy tree (not just direct reports)
            all_subordinates = self._get_all_subordinates(user, commission_plan)

            if all_subordinates:
                for subordinate in all_subordinates:
                    subordinate_orders = self._get_eligible_orders_for_user(subordinate, Invoice, SaleOrder)
                    for order in subordinate_orders:
                        created = self._create_commission_for_user(
                            user=user,  # Commission for current user, not subordinate
                            role=user_role,
                            commission_type='override',
                            order=order,
                            commission_plan=commission_plan,
                            role_config=role_config
                        )
                        commissions_created += created

            if commissions_created > 0:
                total_commissions_created += commissions_created
                plans_processed.append(commission_plan.name)
                import logging
                _logger = logging.getLogger(__name__)
                _logger.info(f'Created {commissions_created} commission(s) for plan {commission_plan.name}')

        # Calculate total and claimable amounts for current user
        claimable_amount = 0
        if total_commissions_created > 0:
            recent_commissions = self.env['sale.commission'].search([
                ('user_id', '=', user.id),
            ], order='create_date desc', limit=total_commissions_created)

            total_amount = sum(recent_commissions.mapped('commission_amount'))
            unpaid_commissions = recent_commissions.filtered(lambda c: c.status == 'unpaid')
            claimable_amount = sum(unpaid_commissions.mapped('commission_amount'))

        message = f'{total_commissions_created} commission(s) créée(s) pour {user.name}'
        if plans_processed:
            message += f' sur {len(plans_processed)} plan(s) ({", ".join(plans_processed)})'

        return {
            'count': total_commissions_created,
            'total_amount': total_amount,
            'claimable_amount': claimable_amount,
            'success': True,
            'message': message
        }

    def _get_eligible_orders_for_user(self, user, Invoice, SaleOrder):
        """Get sale orders eligible for commission for a specific user.

        An order is eligible only if it passes _check_commission_eligibility():
        - All eligible invoices (out_invoice) AND active credit notes are fully paid
        - Sum of eligible invoices is at least the SO total
        - Active credit notes are deducted from the base (net base > 0)
        """
        import logging
        _logger = logging.getLogger(__name__)

        # Get confirmed orders for this user
        orders = SaleOrder.search([
            ('user_id', '=', user.id),
            ('state', 'in', ['sale', 'done']),
        ])

        eligible_orders = SaleOrder.browse()
        for order in orders:
            eligibility = order._check_commission_eligibility()
            if eligibility['eligible']:
                eligible_orders |= order
            else:
                _logger.debug(
                    "=== COMMISSION V2 DASHBOARD === Order %s not eligible: %s",
                    order.name, eligibility['message']
                )

        return eligible_orders

    def _create_commission_for_user(self, user, role, commission_type, order, commission_plan, role_config):
        """Create a single commission record for a user on a specific order.

        Creates ONE commission per SO (not per invoice). The base_amount is the
        SO total (= sum of eligible invoices, validated by _check_commission_eligibility).

        LEGACY SUPPORT: If ANY legacy commission flag is true on the sale order,
        commission generation is completely blocked for that order.

        Returns: 1 if commission created, 0 if already exists or blocked
        """
        import logging
        _logger = logging.getLogger(__name__)

        # LEGACY CHECK: Block commission generation if ANY legacy flag is true
        if (order.x_studio_payee_commercial or
            order.x_studio_payee_directeur_commercial or
            order.x_studio_payee_responsable_commercial):
            _logger.info("Legacy commission flags detected on order %s - commission generation blocked", order.name)
            return 0

        # Skip if the applicable percentage is 0%
        applicable_percentage = (
            role_config.direct_sale_percentage if commission_type == 'direct'
            else role_config.override_percentage
        )
        if not applicable_percentage:
            _logger.debug(
                "Skipping %s commission for %s on order %s: 0%% percentage configured",
                commission_type, user.name, order.name
            )
            return 0

        # Check if commission already exists for this SO + plan + user + role
        existing_commission = self.env['sale.commission'].search([
            ('sale_order_id', '=', order.id),
            ('user_id', '=', user.id),
            ('plan_id', '=', commission_plan.id),
            ('role_id', '=', role.id),
            ('commission_type', '=', commission_type)
        ], limit=1)

        if existing_commission:
            return 0

        # Get eligible invoices for date/period
        eligible_invoices = order.invoice_ids.filtered(
            lambda inv: inv.move_type == 'out_invoice' and inv.state != 'cancel'
        )

        # Use the most recent invoice date for period
        invoice_date = fields.Date.today()
        if eligible_invoices:
            dates = [d for d in eligible_invoices.mapped('invoice_date') if d]
            if dates:
                invoice_date = max(dates)

        period = invoice_date.strftime('%Y-%m')
        # Commission is calculated on the untaxed (HTVA) amount, never on the VAT,
        # net of any active credit notes (avoirs) linked to this order. Eligibility
        # (_check_commission_eligibility) already guarantees those credit notes are
        # paid and do not exceed the invoiced amount.
        credit_notes = order.invoice_ids.filtered(
            lambda inv: inv.move_type == 'out_refund' and inv.state != 'cancel'
        )
        base_amount = order.amount_untaxed - sum(credit_notes.mapped('amount_untaxed'))

        # Create commission record — one per SO, not per invoice
        try:
            self.env['sale.commission'].create({
                'user_id': user.id,
                'role_id': role.id,
                'commission_type': commission_type,
                'sale_order_id': order.id,
                'invoice_id': False,  # Commission covers entire SO
                'plan_id': commission_plan.id,
                'date': invoice_date,
                'period': period,
                'base_amount': base_amount,
                'status': 'unpaid',
                'company_id': order.company_id.id,
                'currency_id': order.currency_id.id,
            })
            _logger.info(
                "=== COMMISSION V2 DASHBOARD === Created commission for %s (%s, %s) - Order: %s, Base: %.2f",
                user.name, role.name, commission_type, order.name, base_amount
            )
            return 1
        except Exception as e:
            _logger.error("Error creating commission for %s on order %s: %s", user.name, order.name, str(e))
            return 0
