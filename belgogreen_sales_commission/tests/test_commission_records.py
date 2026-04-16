# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestCommissionRecords(TransactionCase):
    """Tests for the sale.commission model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        # Create roles
        cls.role_sp = cls.env['sale.commission.role'].create({
            'name': 'Rec Test SP',
            'code': 'RTS',
            'sequence': 10,
            'company_id': cls.company.id,
        })
        cls.role_tl = cls.env['sale.commission.role'].create({
            'name': 'Rec Test TL',
            'code': 'RTL',
            'sequence': 20,
            'company_id': cls.company.id,
        })

        # Create plan with role configs
        cls.plan = cls.env['sale.commission.plan'].create({
            'name': 'Rec Test Plan',
            'type': 'hierarchical',
            'company_id': cls.company.id,
        })
        cls.env['hr.commission.role.config'].create({
            'plan_id': cls.plan.id,
            'role_id': cls.role_sp.id,
            'direct_sale_percentage': 5.0,
            'override_percentage': 0.0,
        })
        cls.env['hr.commission.role.config'].create({
            'plan_id': cls.plan.id,
            'role_id': cls.role_tl.id,
            'direct_sale_percentage': 5.0,
            'override_percentage': 2.0,
        })

        # Create users
        cls.user_sp = cls.env['res.users'].create({
            'name': 'Rec SP User',
            'login': 'test_rec_sp',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.user_tl = cls.env['res.users'].create({
            'name': 'Rec TL User',
            'login': 'test_rec_tl',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

    # ---------------------------------------------------------------
    # Test 1: Commission creation with sequence
    # ---------------------------------------------------------------

    def test_commission_auto_sequence(self):
        """Test that commission gets auto-generated reference"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertNotEqual(commission.name, 'New')
        self.assertTrue(commission.name)

    # ---------------------------------------------------------------
    # Test 2: Commission percentage computation
    # ---------------------------------------------------------------

    def test_commission_percentage_from_role_config_direct(self):
        """Test direct sale percentage is fetched from role config"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'commission_type': 'direct',
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertEqual(commission.commission_percentage, 5.0)

    def test_commission_percentage_from_role_config_override(self):
        """Test override percentage is fetched from role config"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_tl.id,
            'role_id': self.role_tl.id,
            'plan_id': self.plan.id,
            'commission_type': 'override',
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertEqual(commission.commission_percentage, 2.0)

    def test_commission_percentage_override_takes_priority(self):
        """Test that manual percentage override takes priority"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'commission_type': 'direct',
            'base_amount': 1000.0,
            'percentage_override': 8.5,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertEqual(commission.commission_percentage, 8.5)

    # ---------------------------------------------------------------
    # Test 3: Commission amount computation
    # ---------------------------------------------------------------

    def test_commission_amount_computed(self):
        """Test commission amount = base_amount × percentage / 100"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'commission_type': 'direct',
            'base_amount': 10000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        # 10000 × 5% = 500
        self.assertEqual(commission.commission_amount, 500.0)

    def test_commission_amount_with_override(self):
        """Test commission amount with manual percentage override"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_tl.id,
            'role_id': self.role_tl.id,
            'plan_id': self.plan.id,
            'commission_type': 'override',
            'base_amount': 5000.0,
            'percentage_override': 3.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        # 5000 × 3% = 150
        self.assertEqual(commission.commission_amount, 150.0)

    # ---------------------------------------------------------------
    # Test 4: Commission status transitions
    # ---------------------------------------------------------------

    def test_commission_default_status(self):
        """Test that new commission defaults to 'unpaid'"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertEqual(commission.status, 'unpaid')

    def test_commission_cancel(self):
        """Test cancelling a commission"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        commission.action_cancel()
        self.assertEqual(commission.status, 'cancelled')

    # ---------------------------------------------------------------
    # Test 5: Plan required constraint
    # ---------------------------------------------------------------

    def test_auto_commission_without_plan_raises(self):
        """Test that automatic commission without plan raises error"""
        with self.assertRaises(UserError):
            self.env['sale.commission'].create({
                'user_id': self.user_sp.id,
                'role_id': self.role_sp.id,
                'is_adjustment': False,
                'base_amount': 1000.0,
                'currency_id': self.currency.id,
                'company_id': self.company.id,
            })

    def test_manual_commission_without_plan_ok(self):
        """Test that manual commission without plan is allowed"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'is_adjustment': True,
            'base_amount': 1000.0,
            'percentage_override': 10.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertTrue(commission.id)
        self.assertTrue(commission.is_adjustment)

    # ---------------------------------------------------------------
    # Test 6: Role required constraint
    # ---------------------------------------------------------------

    def test_auto_commission_without_role_raises(self):
        """Test that automatic commission without role raises error"""
        with self.assertRaises(UserError):
            self.env['sale.commission'].create({
                'user_id': self.user_sp.id,
                'plan_id': self.plan.id,
                'is_adjustment': False,
                'base_amount': 1000.0,
                'currency_id': self.currency.id,
                'company_id': self.company.id,
            })

    # ---------------------------------------------------------------
    # Test 7: Customer computed field
    # ---------------------------------------------------------------

    def test_customer_from_sale_order(self):
        """Test customer_id is computed from sale order"""
        partner = self.env['res.partner'].create({'name': 'Test Customer'})
        so = self.env['sale.order'].create({
            'partner_id': partner.id,
        })
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'sale_order_id': so.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertEqual(commission.customer_id, partner)

    def test_customer_empty_without_sale_order(self):
        """Test customer_id is empty when no sale order"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'is_adjustment': True,
            'base_amount': 1000.0,
            'percentage_override': 10.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertFalse(commission.customer_id)

    # ---------------------------------------------------------------
    # Test 8: Sale order display computed field
    # ---------------------------------------------------------------

    def test_sale_order_display_single(self):
        """Test display shows order name for single order"""
        partner = self.env['res.partner'].create({'name': 'Display Customer'})
        so = self.env['sale.order'].create({
            'partner_id': partner.id,
        })
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'sale_order_id': so.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertEqual(commission.sale_order_display, so.name)

    def test_sale_order_display_empty(self):
        """Test display is empty when no sale order"""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'is_adjustment': True,
            'base_amount': 500.0,
            'percentage_override': 10.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        self.assertEqual(commission.sale_order_display, '')

    # ---------------------------------------------------------------
    # Test 9: Manual pay action
    # ---------------------------------------------------------------

    def test_manual_pay_plan_commission_unpaid_succeeds(self):
        """Plan commissions in 'unpaid' can be manually marked paid by a manager."""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        # Run as admin (commission manager)
        commission.action_manual_pay()
        self.assertEqual(commission.status, 'paid')
        self.assertTrue(commission.payment_date)
        # No accounting linkage — it's a direct flag
        self.assertFalse(commission.payment_id)

    def test_manual_pay_non_unpaid_raises(self):
        """Commissions past 'unpaid' can't be hijacked into direct-paid."""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        commission.write({'status': 'claimed'})
        with self.assertRaises(UserError):
            commission.action_manual_pay()

    def test_reverse_manual_pay_succeeds(self):
        """Manually-paid commissions can be reverted to 'unpaid'."""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })
        commission.action_manual_pay()
        commission.action_reverse_manual_pay()
        self.assertEqual(commission.status, 'unpaid')
        self.assertFalse(commission.payment_date)

    def test_reverse_manual_pay_on_bill_paid_raises(self):
        """Commissions paid via the PO/bill workflow can't be reversed here."""
        commission = self.env['sale.commission'].create({
            'user_id': self.user_sp.id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'base_amount': 1000.0,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
            'status': 'paid',
            'payment_date': '2026-01-01',
        })
        # Simulate a bill-paid commission by attaching a payment_id.
        # We fake this by creating a minimal account.payment record.
        payment = self.env['account.payment'].create({
            'amount': 1000.0,
            'payment_type': 'outbound',
        })
        commission.write({'payment_id': payment.id})
        with self.assertRaises(UserError):
            commission.action_reverse_manual_pay()
