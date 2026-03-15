# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAccessRights(TransactionCase):
    """Tests to verify that commission module overrides don't break
    standard Odoo operations for users without commission groups.

    This is a regression test for the sudo() fix — ensuring that
    purchase users, accountants, and sales users can perform their
    normal operations without AccessError on commission models.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Create a purchase user (no commission group)
        cls.purchase_user = cls.env['res.users'].create({
            'name': 'Purchase Only User',
            'login': 'test_purchase_only',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'groups_id': [
                (4, cls.env.ref('purchase.group_purchase_user').id),
            ],
        })

        # Create a sales user (no commission group)
        cls.sales_user = cls.env['res.users'].create({
            'name': 'Sales Only User',
            'login': 'test_sales_only',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'groups_id': [
                (4, cls.env.ref('sales_team.group_sale_salesman').id),
            ],
        })

        # Create a vendor for PO
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Test Vendor',
            'supplier_rank': 1,
        })

        # Create a product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'service',
            'list_price': 100.0,
        })

    # ---------------------------------------------------------------
    # Test 1: Purchase user can create and confirm PO
    # ---------------------------------------------------------------

    def test_purchase_user_create_po(self):
        """Test that purchase user without commission group can create a PO"""
        po = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.vendor.id,
        })
        self.env['purchase.order.line'].with_user(self.purchase_user).create({
            'order_id': po.id,
            'product_id': self.product.id,
            'name': 'Test line',
            'product_qty': 1,
            'price_unit': 100.0,
        })
        self.assertTrue(po.id)

    def test_purchase_user_confirm_po(self):
        """Test that purchase user without commission group can confirm a PO
        This is the key regression test for the sudo() fix on button_confirm()
        """
        po = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.vendor.id,
        })
        self.env['purchase.order.line'].with_user(self.purchase_user).create({
            'order_id': po.id,
            'product_id': self.product.id,
            'name': 'Test line',
            'product_qty': 1,
            'price_unit': 100.0,
        })
        # This should NOT raise AccessError on sale.commission.claim
        po.with_user(self.purchase_user).button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_purchase_user_cancel_po(self):
        """Test that purchase user without commission group can cancel a PO"""
        po = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.vendor.id,
        })
        self.env['purchase.order.line'].with_user(self.purchase_user).create({
            'order_id': po.id,
            'product_id': self.product.id,
            'name': 'Test line',
            'product_qty': 1,
            'price_unit': 100.0,
        })
        po.with_user(self.purchase_user).button_confirm()
        # This should NOT raise AccessError
        po.with_user(self.purchase_user).button_cancel()
        self.assertEqual(po.state, 'cancel')

    # ---------------------------------------------------------------
    # Test 2: Purchase user can write to PO
    # ---------------------------------------------------------------

    def test_purchase_user_write_po(self):
        """Test that purchase user can edit PO without AccessError on claim_ids"""
        po = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.vendor.id,
        })
        # Writing to PO triggers the write() override that checks claim_ids
        po.with_user(self.purchase_user).write({
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'New line',
                'product_qty': 2,
                'price_unit': 200.0,
            })]
        })
        self.assertEqual(len(po.order_line), 1)

    # ---------------------------------------------------------------
    # Test 3: Sales user can view sale orders with commission fields
    # ---------------------------------------------------------------

    def test_sales_user_view_sale_order(self):
        """Test that sales user can access commission_count on sale order"""
        customer = self.env['res.partner'].create({'name': 'Test Customer SO'})
        so = self.env['sale.order'].with_user(self.sales_user).create({
            'partner_id': customer.id,
        })
        # Accessing commission_count should not raise AccessError
        count = so.with_user(self.sales_user).commission_count
        self.assertEqual(count, 0)

    # ---------------------------------------------------------------
    # Test 4: User profile commission stats
    # ---------------------------------------------------------------

    def test_user_commission_stats_no_access_error(self):
        """Test that user without commission group can read commission stats"""
        # Accessing computed fields should not raise AccessError
        user = self.purchase_user
        self.assertEqual(user.commission_count, 0)
        self.assertEqual(user.active_commission_count, 0)
