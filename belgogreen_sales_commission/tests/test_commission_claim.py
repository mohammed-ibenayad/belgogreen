# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestCommissionClaim(TransactionCase):
    """Tests for the sale.commission.claim model and commission.deduction model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        # Create roles and plan
        cls.role_sp = cls.env['sale.commission.role'].create({
            'name': 'Claim Test SP',
            'code': 'CTS',
            'sequence': 10,
            'company_id': cls.company.id,
        })

        cls.plan = cls.env['bgg.commission.plan'].create({
            'name': 'Claim Test Plan',
            'company_id': cls.company.id,
        })
        cls.env['hr.commission.role.config'].create({
            'plan_id': cls.plan.id,
            'role_id': cls.role_sp.id,
            'direct_sale_percentage': 5.0,
            'override_percentage': 0.0,
        })

        # Create user with commission group
        cls.commission_user = cls.env['res.users'].create({
            'name': 'Claim Test User',
            'login': 'test_claim_user',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(4, cls.env.ref('belgogreen_sales_commission.group_commission_user').id)],
        })

        cls.commission_manager = cls.env['res.users'].create({
            'name': 'Claim Test Manager',
            'login': 'test_claim_manager',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(4, cls.env.ref('belgogreen_sales_commission.group_commission_manager').id)],
        })

    def _create_commission(self, user=None, amount=1000.0):
        """Helper to create a commission record"""
        return self.env['sale.commission'].create({
            'user_id': (user or self.commission_user).id,
            'role_id': self.role_sp.id,
            'plan_id': self.plan.id,
            'commission_type': 'direct',
            'base_amount': amount,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
        })

    # ---------------------------------------------------------------
    # Test 1: Claim creation
    # ---------------------------------------------------------------

    def test_claim_creation_auto_sequence(self):
        """Test that claim gets auto-generated reference"""
        commission = self._create_commission()
        claim = self.env['sale.commission.claim'].with_user(self.commission_user).create({
            'user_id': self.commission_user.id,
            'commission_ids': [(6, 0, [commission.id])],
        })
        self.assertNotEqual(claim.name, 'New')
        self.assertEqual(claim.state, 'draft')

    def test_claim_total_amount_computed(self):
        """Test that claim total is sum of commission amounts"""
        c1 = self._create_commission(amount=1000.0)  # 5% of 1000 = 50
        c2 = self._create_commission(amount=2000.0)  # 5% of 2000 = 100
        claim = self.env['sale.commission.claim'].create({
            'user_id': self.commission_user.id,
            'commission_ids': [(6, 0, [c1.id, c2.id])],
        })
        self.assertEqual(claim.total_amount, 150.0)  # 50 + 100
        self.assertEqual(claim.commission_count, 2)

    # ---------------------------------------------------------------
    # Test 2: Claim submission
    # ---------------------------------------------------------------

    def test_claim_submit_updates_commission_status(self):
        """Test that submitting claim updates commissions to 'claimed'"""
        commission = self._create_commission()
        claim = self.env['sale.commission.claim'].with_user(self.commission_user).create({
            'user_id': self.commission_user.id,
            'commission_ids': [(6, 0, [commission.id])],
        })
        claim.action_submit()
        self.assertEqual(claim.state, 'pending')
        self.assertEqual(commission.status, 'claimed')

    def test_claim_submit_without_commissions_raises(self):
        """Test that submitting empty claim raises error"""
        claim = self.env['sale.commission.claim'].with_user(self.commission_user).create({
            'user_id': self.commission_user.id,
        })
        with self.assertRaises(UserError):
            claim.action_submit()

    def test_claim_submit_with_cancelled_commission_raises(self):
        """Submitting a claim that still contains a cancelled commission must
        raise instead of silently resurrecting it to 'claimed'."""
        active = self._create_commission()
        cancelled = self._create_commission()
        cancelled.action_cancel()
        self.assertEqual(cancelled.status, 'cancelled')

        claim = self.env['sale.commission.claim'].with_user(self.commission_user).create({
            'user_id': self.commission_user.id,
            'commission_ids': [(6, 0, [active.id, cancelled.id])],
        })
        with self.assertRaises(UserError):
            claim.action_submit()

        # Cancelled commission must remain cancelled; claim must stay draft.
        self.assertEqual(cancelled.status, 'cancelled')
        self.assertEqual(active.status, 'unpaid')
        self.assertEqual(claim.state, 'draft')

    # ---------------------------------------------------------------
    # Test 3: Claim rejection
    # ---------------------------------------------------------------

    def test_claim_reject_resets_commission_status(self):
        """Test that rejecting claim resets commissions to 'unpaid'"""
        commission = self._create_commission()
        claim = self.env['sale.commission.claim'].create({
            'user_id': self.commission_user.id,
            'commission_ids': [(6, 0, [commission.id])],
        })
        claim.action_submit()
        self.assertEqual(commission.status, 'claimed')

        claim.with_user(self.commission_manager).action_reject()
        self.assertEqual(claim.state, 'rejected')
        self.assertEqual(commission.status, 'unpaid')

    # ---------------------------------------------------------------
    # Test 4: Draft claim deletion
    # ---------------------------------------------------------------

    def test_delete_draft_claim(self):
        """Test that draft claims can be deleted by owner"""
        commission = self._create_commission()
        claim = self.env['sale.commission.claim'].with_user(self.commission_user).create({
            'user_id': self.commission_user.id,
            'commission_ids': [(6, 0, [commission.id])],
        })
        claim.with_user(self.commission_user).action_delete_draft()
        self.assertFalse(claim.exists())

    def test_delete_non_draft_claim_raises(self):
        """Test that non-draft claims cannot be deleted"""
        commission = self._create_commission()
        claim = self.env['sale.commission.claim'].with_user(self.commission_user).create({
            'user_id': self.commission_user.id,
            'commission_ids': [(6, 0, [commission.id])],
        })
        claim.action_submit()  # Move to pending
        with self.assertRaises(UserError):
            claim.with_user(self.commission_user).action_delete_draft()

    # ---------------------------------------------------------------
    # Test 5: Deduction creation and validation
    # ---------------------------------------------------------------

    def test_deduction_creation(self):
        """Test creating a commission deduction"""
        deduction = self.env['commission.deduction'].create({
            'user_id': self.commission_user.id,
            'deduction_type': 'down_payment',
            'deduction_category': 'mandatory',
            'amount': 100.0,
            'currency_id': self.currency.id,
            'description': 'Test deduction',
        })
        self.assertEqual(deduction.state, 'pending')
        self.assertNotEqual(deduction.name, 'New')

    def test_deduction_zero_amount_raises(self):
        """Test that zero amount deduction raises error"""
        with self.assertRaises(ValidationError):
            self.env['commission.deduction'].create({
                'user_id': self.commission_user.id,
                'deduction_type': 'service_fee',
                'deduction_category': 'mandatory',
                'amount': 0.0,
                'currency_id': self.currency.id,
                'description': 'Zero deduction',
            })

    def test_deduction_cancel(self):
        """Test cancelling a pending deduction"""
        deduction = self.env['commission.deduction'].create({
            'user_id': self.commission_user.id,
            'deduction_type': 'down_payment',
            'deduction_category': 'optional',
            'amount': 50.0,
            'currency_id': self.currency.id,
            'description': 'Cancellable deduction',
        })
        deduction.action_cancel()
        self.assertEqual(deduction.state, 'cancelled')

    # ---------------------------------------------------------------
    # Test 6: Net amount validation
    # ---------------------------------------------------------------

    def test_negative_net_amount_blocks_submission(self):
        """Test that claim with negative net cannot be submitted"""
        commission = self._create_commission(amount=100.0)  # 5% of 100 = 5

        # Create mandatory deduction larger than commission
        self.env['commission.deduction'].create({
            'user_id': self.commission_user.id,
            'deduction_type': 'down_payment',
            'deduction_category': 'mandatory',
            'amount': 10.0,
            'currency_id': self.currency.id,
            'description': 'Large deduction',
            'company_id': self.company.id,
        })

        claim = self.env['sale.commission.claim'].create({
            'user_id': self.commission_user.id,
            'commission_ids': [(6, 0, [commission.id])],
        })

        # Net = 5 (commission) - 10 (deduction) = -5 → should fail
        with self.assertRaises(UserError):
            claim.action_submit()
