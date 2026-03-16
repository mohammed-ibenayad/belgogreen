# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestResPartner(TransactionCase):
    """Test suite for res.partner phone_2 field"""

    def test_phone_2_field_exists(self):
        """Test that phone_2 field is available on res.partner"""
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'phone': '+32412345678',
            'phone_2': '+32498765432',
        })
        self.assertEqual(partner.phone_2, '+32498765432',
                        "phone_2 field should store second phone number")

    def test_phone_2_optional(self):
        """Test that phone_2 is not required"""
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'phone': '+32412345678',
        })
        self.assertFalse(partner.phone_2,
                        "phone_2 should be False when not provided")
