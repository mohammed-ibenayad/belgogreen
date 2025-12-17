# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class CommissionDashboard(models.TransientModel):
    _name = 'commission.dashboard'
    _description = 'Commission Dashboard'

    @api.model
    def get_dashboard_data(self):
        """Get all dashboard data for the current user"""
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
        my_pending = sum(my_commissions.filtered(lambda c: c.payment_status == 'unpaid').mapped('commission_amount'))
        my_paid = sum(my_commissions.filtered(lambda c: c.payment_status == 'paid').mapped('commission_amount'))

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
        team_pending = sum(team_commissions.filtered(lambda c: c.payment_status == 'unpaid').mapped('commission_amount'))
        team_members_count = len(set(team_commissions.mapped('user_id')))

        # Pending actions (claims to approve)
        pending_claims = self.env['sale.commission.claim'].search_count([
            ('state', '=', 'pending'),
            ('user_id.commission_manager_id', '=', self.env.user.id)
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
            'hierarchy_issues': self.env.user.subordinate_count if hasattr(self.env.user, 'has_hierarchy_anomaly') and self.env.user.has_hierarchy_anomaly else 0,
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

        state_distribution = {
            'pending': sum(my_commissions.filtered(lambda c: c.payment_status == 'unpaid').mapped('commission_amount')),
            'approved': sum(my_commissions.filtered(lambda c: c.payment_status == 'claimed').mapped('commission_amount')),
            'paid': sum(my_commissions.filtered(lambda c: c.payment_status == 'paid').mapped('commission_amount')),
            'cancelled': sum(my_commissions.filtered(lambda c: c.payment_status == 'cancelled').mapped('commission_amount')),
        }

        return {
            'monthly_trend': monthly_data,
            'state_distribution': state_distribution,
        }

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

        # Check if user has commission plan assignment
        user_assignment = self.env['sale.commission.plan.user'].search([
            ('user_id', '=', user.id),
            ('plan_id.state', '=', 'approved'),
            ('plan_id.type', '=', 'hierarchical'),
        ], limit=1)

        if not user_assignment:
            return {
                'count': 0,
                'total_amount': 0,
                'claimable_amount': 0,
                'success': False,
                'message': 'You are not assigned to any approved hierarchical commission plan'
            }

        commission_plan = user_assignment.plan_id
        user_role = user_assignment.role_id

        # Get role configuration for current user
        role_config = self.env['hr.commission.role.config'].search([
            ('plan_id', '=', commission_plan.id),
            ('role_id', '=', user_role.id),
            ('active', '=', True)
        ], limit=1)

        if not role_config:
            return {
                'count': 0,
                'total_amount': 0,
                'claimable_amount': 0,
                'success': False,
                'message': f'No active configuration found for role {user_role.name} in the commission plan'
            }

        SaleOrder = self.env['sale.order']
        Invoice = self.env['account.move']

        commissions_created = 0
        total_amount = 0

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
        subordinate_assignments = self.env['sale.commission.plan.user'].search([
            ('manager_id', '=', user.id),
            ('plan_id', '=', commission_plan.id)
        ])
        subordinate_ids = subordinate_assignments.mapped('user_id').ids

        if subordinate_ids:
            subordinates = self.env['res.users'].browse(subordinate_ids)
            for subordinate in subordinates:
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

        # Calculate total and claimable amounts for current user
        claimable_amount = 0
        if commissions_created > 0:
            recent_commissions = self.env['sale.commission'].search([
                ('user_id', '=', user.id),
            ], order='create_date desc', limit=commissions_created)

            total_amount = sum(recent_commissions.mapped('commission_amount'))
            unpaid_commissions = recent_commissions.filtered(lambda c: c.payment_status == 'unpaid')
            claimable_amount = sum(unpaid_commissions.mapped('commission_amount'))

        return {
            'count': commissions_created,
            'total_amount': total_amount,
            'claimable_amount': claimable_amount,
            'success': True,
            'message': f'{commissions_created} commission(s) created for {user.name}'
        }

    def _get_eligible_orders_for_user(self, user, Invoice, SaleOrder):
        """Get sale orders with paid invoices for a specific user"""
        # Get all paid invoices
        paid_invoices = Invoice.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['paid', 'in_payment']),
            ('invoice_origin', '!=', False),
        ])

        # Filter to get orders from these invoices that belong to the user
        order_ids = set()
        for invoice in paid_invoices:
            sale_orders = SaleOrder.search([
                ('name', '=', invoice.invoice_origin),
                ('user_id', '=', user.id),
                ('state', 'in', ['sale', 'done']),
            ])
            if sale_orders:
                order_ids.update(sale_orders.ids)

        return SaleOrder.browse(list(order_ids))

    def _create_commission_for_user(self, user, role, commission_type, order, commission_plan, role_config):
        """Create a single commission record for a user on a specific order

        Returns: 1 if commission created, 0 if already exists or error
        """
        # Get paid invoices for this order
        paid_invoices = order.invoice_ids.filtered(
            lambda inv: inv.move_type == 'out_invoice'
            and inv.state == 'posted'
            and inv.payment_state in ['paid', 'in_payment']
        )

        if not paid_invoices:
            return 0

        commissions_created = 0
        for invoice in paid_invoices:
            # Check if commission already exists
            existing_commission = self.env['sale.commission'].search([
                ('invoice_id', '=', invoice.id),
                ('sale_order_id', '=', order.id),
                ('user_id', '=', user.id),
                ('role_id', '=', role.id),
                ('commission_type', '=', commission_type)
            ], limit=1)

            if existing_commission:
                continue

            # Calculate period
            period = invoice.invoice_date.strftime('%Y-%m') if invoice.invoice_date else fields.Date.today().strftime('%Y-%m')
            base_amount = invoice.amount_total

            # Create commission record
            try:
                self.env['sale.commission'].create({
                    'user_id': user.id,
                    'role_id': role.id,
                    'commission_type': commission_type,
                    'sale_order_id': order.id,
                    'invoice_id': invoice.id,
                    'plan_id': commission_plan.id,
                    'date': invoice.invoice_date or fields.Date.today(),
                    'period': period,
                    'base_amount': base_amount,
                    'payment_status': 'unpaid',
                    'state': 'confirmed',
                    'company_id': order.company_id.id,
                    'currency_id': order.currency_id.id,
                })
                commissions_created += 1
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error("Error creating commission for %s on order %s: %s", user.name, order.name, str(e))

        return commissions_created
