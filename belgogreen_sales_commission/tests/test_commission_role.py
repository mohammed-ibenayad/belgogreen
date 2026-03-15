# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestCommissionRole(TransactionCase):
    """Tests for the sale.commission.role model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.role_salesperson = cls.env['sale.commission.role'].create({
            'name': 'Test Salesperson',
            'code': 'TSP',
            'sequence': 10,
            'company_id': cls.company.id,
            'is_base_role': True,
        })

        cls.role_team_leader = cls.env['sale.commission.role'].create({
            'name': 'Test Team Leader',
            'code': 'TTL',
            'sequence': 20,
            'company_id': cls.company.id,
        })

        cls.role_director = cls.env['sale.commission.role'].create({
            'name': 'Test Director',
            'code': 'TDR',
            'sequence': 30,
            'company_id': cls.company.id,
            'requires_manager': False,
        })

    # ---------------------------------------------------------------
    # Test 1: Role creation and basic fields
    # ---------------------------------------------------------------

    def test_role_creation(self):
        """Test that roles are created with correct values"""
        self.assertEqual(self.role_salesperson.name, 'Test Salesperson')
        self.assertEqual(self.role_salesperson.code, 'TSP')
        self.assertEqual(self.role_salesperson.sequence, 10)
        self.assertTrue(self.role_salesperson.is_base_role)
        self.assertTrue(self.role_salesperson.active)

    def test_role_ordering(self):
        """Test that roles are ordered by sequence then name"""
        roles = self.env['sale.commission.role'].search([
            ('code', 'in', ['TSP', 'TTL', 'TDR'])
        ], order='sequence, name')
        self.assertEqual(roles[0], self.role_salesperson)
        self.assertEqual(roles[1], self.role_team_leader)
        self.assertEqual(roles[2], self.role_director)

    # ---------------------------------------------------------------
    # Test 2: Unique code constraint
    # ---------------------------------------------------------------

    def test_duplicate_code_same_company_raises(self):
        """Test that duplicate code in same company raises ValidationError"""
        with self.assertRaises(ValidationError):
            self.env['sale.commission.role'].create({
                'name': 'Another Salesperson',
                'code': 'TSP',  # Duplicate code
                'sequence': 15,
                'company_id': self.company.id,
            })

    def test_duplicate_code_different_company_ok(self):
        """Test that same code in different company is allowed"""
        other_company = self.env['res.company'].create({'name': 'Other Company'})
        role = self.env['sale.commission.role'].create({
            'name': 'Salesperson Other',
            'code': 'TSP',  # Same code, different company
            'sequence': 10,
            'company_id': other_company.id,
        })
        self.assertTrue(role.id)

    # ---------------------------------------------------------------
    # Test 3: Unique name constraint
    # ---------------------------------------------------------------

    def test_duplicate_name_same_company_raises(self):
        """Test that duplicate name in same company raises ValidationError"""
        with self.assertRaises(ValidationError):
            self.env['sale.commission.role'].create({
                'name': 'Test Salesperson',  # Duplicate name
                'code': 'TSP2',
                'sequence': 15,
                'company_id': self.company.id,
            })

    # ---------------------------------------------------------------
    # Test 4: Sequence constraint
    # ---------------------------------------------------------------

    def test_negative_sequence_raises(self):
        """Test that negative sequence raises ValidationError"""
        with self.assertRaises(ValidationError):
            self.env['sale.commission.role'].create({
                'name': 'Bad Role',
                'code': 'BAD',
                'sequence': -1,
                'company_id': self.company.id,
            })

    # ---------------------------------------------------------------
    # Test 5: Deletion protection
    # ---------------------------------------------------------------

    def test_delete_unused_role(self):
        """Test that unused role can be deleted"""
        role = self.env['sale.commission.role'].create({
            'name': 'Deletable Role',
            'code': 'DEL',
            'sequence': 5,
            'company_id': self.company.id,
        })
        role.unlink()
        self.assertFalse(role.exists())
