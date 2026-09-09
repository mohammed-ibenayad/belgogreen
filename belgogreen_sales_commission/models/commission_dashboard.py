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

