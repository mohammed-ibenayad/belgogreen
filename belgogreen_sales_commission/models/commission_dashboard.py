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
        active_plans = self.env['sale.commission.plan'].search([
            ('is_hierarchical', '=', True),
            ('state', '=', 'approved'),
        ], limit=1)

        return bool(active_plans)

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

        Only generates commissions for orders with paid invoices
        Returns count and total amount of generated commissions
        """
        user = self.env.user

        # Find commission plan first
        commission_plan = self.env['sale.commission.plan'].search([
            ('is_hierarchical', '=', True),
            ('state', '=', 'approved'),
            ('company_id', '=', user.company_id.id)
        ], limit=1)

        if not commission_plan:
            return {
                'count': 0,
                'total_amount': 0,
                'success': False,
                'message': 'No approved hierarchical commission plan found'
            }

        # Find confirmed sales orders for this user that have paid invoices
        SaleOrder = self.env['sale.order']
        Invoice = self.env['account.move']

        # Get all paid invoices for sale orders belonging to current user
        paid_invoices = Invoice.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['paid', 'in_payment']),
            ('invoice_origin', '!=', False),  # Has a source document
        ])

        # Filter to get orders from these invoices that belong to current user
        order_ids = set()
        for invoice in paid_invoices:
            # Get the sale order from this invoice
            sale_orders = SaleOrder.search([
                ('name', '=', invoice.invoice_origin),
                ('user_id', '=', user.id),
                ('state', 'in', ['sale', 'done']),
            ])
            if sale_orders:
                order_ids.update(sale_orders.ids)

        if not order_ids:
            return {
                'count': 0,
                'total_amount': 0,
                'success': True,
                'message': 'No orders with paid invoices found'
            }

        orders = SaleOrder.browse(list(order_ids))
        total_commissions_created = 0
        total_amount = 0
        processed_orders = []

        for order in orders:
            # Generate commissions for this order (will create for entire hierarchy)
            try:
                result = order._generate_commissions()
                if result['success'] and result['commissions_created'] > 0:
                    total_commissions_created += result['commissions_created']
                    processed_orders.append(order.id)
            except Exception as e:
                # Log error but continue processing other orders
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error("Error generating commissions for order %s: %s", order.name, str(e))
                continue

        # Calculate total amount of commissions created for this user
        if total_commissions_created > 0:
            # Get commissions created for current user from processed orders
            recent_commissions = self.env['sale.commission'].search([
                ('user_id', '=', user.id),
                ('sale_order_id', 'in', processed_orders),
            ], order='create_date desc', limit=total_commissions_created)

            total_amount = sum(recent_commissions.mapped('commission_amount'))

        return {
            'count': total_commissions_created,
            'total_amount': total_amount,
            'success': True,
            'message': f'{total_commissions_created} commission(s) created from {len(processed_orders)} order(s)'
        }
