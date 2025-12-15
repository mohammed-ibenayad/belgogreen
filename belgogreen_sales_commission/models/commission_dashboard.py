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

        # Get team commissions (if user is a manager)
        team_commissions = self.env['sale.commission'].search([
            ('user_id.commission_manager_id', '=', user.id)
        ])

        # Check if user manages a team
        has_team = len(team_commissions.mapped('user_id')) > 0

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

        return {
            'kpis': kpis,
            'charts': chart_data,
            'currency': currency_info,
            'user_info': {
                'name': user.name,
                'role': user.commission_role_id.name if user.commission_role_id else 'No Role',
                'manager': user.commission_manager_id.name if user.commission_manager_id else None,
                'has_team': has_team,
                'has_active_plan': has_active_plan,
            }
        }

    def _user_has_active_commission_plan(self, user):
        """Check if user is in an active commission plan"""
        # Check if user has a commission role and is part of an active hierarchical plan
        if not user.commission_role_id:
            return False

        # Check if there's an active plan for the user's role
        active_plans = self.env['hr.commission.plan'].search([
            ('commission_role_id', '=', user.commission_role_id.id),
            ('active', '=', True),
        ])

        return len(active_plans) > 0

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

        Only generates direct sales and override commissions (not team commissions)
        Returns count and total amount of generated commissions
        """
        user = self.env.user

        # Find all confirmed sales orders for this user with paid invoices
        SaleOrder = self.env['sale.order']
        orders = SaleOrder.search([
            ('state', 'in', ['sale', 'done']),
            ('user_id', '=', user.id),  # Orders owned by current user
        ])

        total_commissions_created = 0
        total_amount = 0

        for order in orders:
            # Generate commissions for this order (will create for entire hierarchy)
            try:
                result = order._generate_commissions()
                if result['success']:
                    total_commissions_created += result['commissions_created']
            except Exception as e:
                # Log error but continue processing other orders
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error("Error generating commissions for order %s: %s", order.name, str(e))
                continue

        # Calculate total amount of commissions created for this user
        if total_commissions_created > 0:
            # Get commissions created in this session for current user
            recent_commissions = self.env['sale.commission'].search([
                ('user_id', '=', user.id),
                ('sale_order_id', 'in', orders.ids),
            ], order='create_date desc', limit=total_commissions_created)

            total_amount = sum(recent_commissions.mapped('commission_amount'))

        return {
            'count': total_commissions_created,
            'total_amount': total_amount,
            'success': True,
        }
