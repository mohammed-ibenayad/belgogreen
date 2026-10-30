# -*- coding: utf-8 -*-

from unittest.mock import patch

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestCommissionPaidStates(AccountTestInvoicingCommon):
    """Commissions follow the invoice payment state.

    On Community a payment registered by hand makes the invoice 'paid'. The
    'in_payment' state (payment posted, not yet matched with a bank statement)
    only exists when a module enables it: Enterprise accounting today, OCA
    account_in_payment later. It counts as paid unless the system parameter
    belgogreen_sales_commission.count_in_payment_as_paid is False."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.ICP = cls.env['ir.config_parameter'].sudo()
        # The accounting test user configures the plan: make it commission manager
        cls.env.user.group_ids = [Command.link(
            cls.env.ref('belgogreen_sales_commission.group_commission_manager').id)]

        cls.salesperson = cls.env['res.users'].create({
            'name': 'Paid States Salesperson',
            'login': 'test_paid_states_sp',
            'company_id': cls.company.id,
            'company_ids': [Command.set(cls.company.ids)],
            'group_ids': [Command.link(cls.env.ref('sales_team.group_sale_salesman').id)],
        })
        role = cls.env['sale.commission.role'].create({
            'name': 'Paid States Seller',
            'code': 'PSS',
            'sequence': 10,
            'company_id': cls.company.id,
        })
        cls.plan = cls.env['bgg.commission.plan'].create({
            'name': 'Paid States Plan',
            'company_id': cls.company.id,
            'role_config_ids': [Command.create({
                'role_id': role.id,
                'direct_sale_percentage': 5.0,
                'override_percentage': 0.0,
            })],
            'user_ids': [Command.create({
                'user_id': cls.salesperson.id,
                'role_id': role.id,
            })],
        })
        cls.plan.action_approve()

        cls.product_a.invoice_policy = 'order'
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner_a.id,
            'user_id': cls.salesperson.id,
            'company_id': cls.company.id,
            'order_line': [Command.create({
                'product_id': cls.product_a.id,
                'product_uom_qty': 1,
                'price_unit': 1000.0,
                'tax_ids': [Command.clear()],
            })],
        })
        cls.order.action_confirm()
        cls.invoice = cls.order._create_invoices()
        cls.invoice.action_post()

    def _register_payment(self, in_payment=False):
        """Register the full payment by hand. With in_payment=True, behave like
        Enterprise accounting / OCA account_in_payment: the invoice stays
        'in_payment' until the payment is matched with a bank statement."""
        register = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=self.invoice.ids,
        ).create({'payment_date': self.invoice.invoice_date})
        if in_payment:
            with patch.object(type(self.env['account.move']), '_get_invoice_in_payment_state',
                              lambda move: 'in_payment'):
                register._create_payments()
                # payment_state is recomputed lazily: do it while patched
                self.env.flush_all()
            self.assertEqual(self.invoice.payment_state, 'in_payment')
        else:
            register._create_payments()
            self.assertEqual(self.invoice.payment_state, 'paid')

    def test_paid_states_default(self):
        """By default 'paid' and 'in_payment' both count as paid"""
        self.assertEqual(self.env['account.move']._get_commission_paid_states(), ('paid', 'in_payment'))

    def test_paid_states_parameter_off(self):
        """With the parameter set to False only 'paid' counts"""
        self.ICP.set_param('belgogreen_sales_commission.count_in_payment_as_paid', 'False')
        self.assertEqual(self.env['account.move']._get_commission_paid_states(), ('paid',))

    def test_unpaid_invoice_blocks_generation(self):
        """A posted but unpaid invoice does not generate commissions"""
        self.assertFalse(self.invoice._is_paid_for_commission())
        result = self.order._generate_commissions()
        self.assertFalse(result.get('success'))
        self.assertFalse(self.order.sudo().commission_ids)

    def test_registered_payment_generates_commission(self):
        """On Community a payment entered by hand makes the invoice paid"""
        self._register_payment()
        result = self.order._generate_commissions()
        self.assertTrue(result.get('success'), result.get('message'))
        self.assertEqual(len(self.order.sudo().commission_ids), 1)

    def test_in_payment_generates_commission(self):
        """An invoice "In payment" generates the commission (5% of 1000)"""
        self._register_payment(in_payment=True)
        self.assertTrue(self.invoice._is_paid_for_commission())
        result = self.order._generate_commissions()
        self.assertTrue(result.get('success'), result.get('message'))
        commission = self.order.sudo().commission_ids
        self.assertEqual(len(commission), 1)
        self.assertEqual(commission.user_id, self.salesperson)
        self.assertEqual(commission.plan_id, self.plan)
        self.assertAlmostEqual(commission.commission_amount, 50.0)
        self.assertTrue(commission.can_be_paid)

    def test_in_payment_not_counted_when_disabled(self):
        """With the parameter off, "In payment" still blocks generation"""
        self.ICP.set_param('belgogreen_sales_commission.count_in_payment_as_paid', 'False')
        self._register_payment(in_payment=True)
        self.assertFalse(self.invoice._is_paid_for_commission())
        result = self.order._generate_commissions()
        self.assertFalse(result.get('success'))
        self.assertFalse(self.order.sudo().commission_ids)

    def test_legacy_studio_flag_blocks_generation(self):
        """The former Studio flag 'Payée Commercial' still blocks generation"""
        self.order.x_studio_payee_commercial = True
        self._register_payment()
        self.order._generate_commissions()
        self.assertFalse(self.order.sudo().commission_ids)
