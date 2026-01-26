# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestProjectProject(TransactionCase):
    """
    Test suite for project.project model automation rules
    Tests 1 automation rule: Update Project Folder Name
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Skip tests if documents module not installed
        if 'documents.folder' not in cls.env:
            cls.skipTest(cls, "Documents module not installed")
            return

        # Create test customer
        cls.test_customer = cls.env['res.partner'].create({
            'name': 'Test Customer For Project',
            'email': 'customer@project.com',
        })

        # Create product for sale order
        cls.test_product = cls.env['product.product'].create({
            'name': 'Project Service Product',
            'type': 'service',
            'service_tracking': 'task_in_project',
            'list_price': 1000.0,
        })

        # Create sale order
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.test_customer.id,
            'order_line': [(0, 0, {
                'product_id': cls.test_product.id,
                'product_uom_qty': 1,
                'price_unit': 1000.0,
            })],
        })

        # Confirm sale order
        cls.sale_order.action_confirm()

        # Get the sale order line
        cls.sale_order_line = cls.sale_order.order_line[0]

    # ========================
    # Test 1: Update Project Folder Name
    # ========================

    def test_folder_renamed_on_project_create(self):
        """Test documents folder renamed on project creation"""
        # Create documents folder
        documents_folder = self.env['documents.folder'].create({
            'name': 'Original Folder Name',
        })

        # Create project linked to sale order
        project = self.env['project.project'].create({
            'name': 'Test Project',
            'sale_line_id': self.sale_order_line.id,
            'documents_folder_id': documents_folder.id,
        })

        # Expected folder name format: "SO Name - Projet - Customer Name"
        expected_name = f"{self.sale_order.name} - Projet - {self.test_customer.name}"

        # Assert folder name updated
        self.assertEqual(documents_folder.name, expected_name,
                        f"Folder name should be '{expected_name}'")

    def test_folder_rename_with_different_customer(self):
        """Test folder name includes correct customer name"""
        # Create different customer
        customer2 = self.env['res.partner'].create({
            'name': 'Different Customer',
        })

        # Create new sale order with different customer
        sale_order2 = self.env['sale.order'].create({
            'partner_id': customer2.id,
            'order_line': [(0, 0, {
                'product_id': self.test_product.id,
                'product_uom_qty': 1,
                'price_unit': 1000.0,
            })],
        })
        sale_order2.action_confirm()

        # Create documents folder
        documents_folder = self.env['documents.folder'].create({
            'name': 'Original Folder Name',
        })

        # Create project
        project = self.env['project.project'].create({
            'name': 'Test Project 2',
            'sale_line_id': sale_order2.order_line[0].id,
            'documents_folder_id': documents_folder.id,
        })

        # Assert customer name in folder name
        self.assertIn(customer2.name, documents_folder.name,
                     "Folder name should contain customer name")
        self.assertIn(sale_order2.name, documents_folder.name,
                     "Folder name should contain sale order name")

    def test_folder_rename_handles_missing_sale_order(self):
        """Test graceful handling when project has no sale order"""
        # Create documents folder
        documents_folder = self.env['documents.folder'].create({
            'name': 'No Sale Order Folder',
        })

        original_name = documents_folder.name

        # Create project without sale order
        project = self.env['project.project'].create({
            'name': 'Project Without Sale Order',
            'documents_folder_id': documents_folder.id,
        })

        # Assert folder name unchanged (no error occurred)
        self.assertEqual(documents_folder.name, original_name,
                        "Folder name should remain unchanged when no sale order")

    def test_folder_rename_handles_missing_folder(self):
        """Test graceful handling when project has no documents folder"""
        # Create project without documents folder
        project = self.env['project.project'].create({
            'name': 'Project Without Folder',
            'sale_line_id': self.sale_order_line.id,
        })

        # Assert no error occurred
        self.assertTrue(project.id, "Project should be created successfully")

    def test_folder_rename_not_on_update(self):
        """Test that folder rename only happens when folder is added, not on other updates"""
        # Create documents folder
        documents_folder = self.env['documents.folder'].create({
            'name': 'Original Folder Name',
        })

        # Create project
        project = self.env['project.project'].create({
            'name': 'Test Project',
            'sale_line_id': self.sale_order_line.id,
            'documents_folder_id': documents_folder.id,
        })

        # Get the folder name after creation
        folder_name_after_create = documents_folder.name

        # Manually change folder name
        documents_folder.write({'name': 'Manually Changed Name'})

        # Update project (not adding/changing documents_folder_id)
        project.write({'name': 'Updated Project Name'})

        # Assert folder name NOT changed back
        # The automation only triggers when documents_folder_id is being set
        self.assertEqual(documents_folder.name, 'Manually Changed Name',
                        "Folder name should not change on unrelated project updates")

    def test_folder_name_format_is_correct(self):
        """Test that folder name format matches exactly: 'SO Name - Projet - Customer Name'"""
        # Create documents folder
        documents_folder = self.env['documents.folder'].create({
            'name': 'Test Folder',
        })

        # Create project
        project = self.env['project.project'].create({
            'name': 'Format Test Project',
            'sale_line_id': self.sale_order_line.id,
            'documents_folder_id': documents_folder.id,
        })

        # Assert format
        self.assertIn(' - Projet - ', documents_folder.name,
                     "Folder name should contain ' - Projet - ' separator")
        self.assertTrue(documents_folder.name.startswith(self.sale_order.name),
                       "Folder name should start with sale order name")
        self.assertTrue(documents_folder.name.endswith(self.test_customer.name),
                       "Folder name should end with customer name")

    # ========================
    # Integration Tests
    # ========================

    def test_batch_create_projects(self):
        """Test that automation works with batch project creation"""
        # Create multiple folders
        folder1 = self.env['documents.folder'].create({'name': 'Folder 1'})
        folder2 = self.env['documents.folder'].create({'name': 'Folder 2'})

        # Create multiple projects at once
        projects = self.env['project.project'].create([
            {
                'name': 'Batch Project 1',
                'sale_line_id': self.sale_order_line.id,
                'documents_folder_id': folder1.id,
            },
            {
                'name': 'Batch Project 2',
                'sale_line_id': self.sale_order_line.id,
                'documents_folder_id': folder2.id,
            },
        ])

        expected_name = f"{self.sale_order.name} - Projet - {self.test_customer.name}"

        # Assert both folders renamed
        self.assertEqual(folder1.name, expected_name,
                        "First folder should be renamed")
        self.assertEqual(folder2.name, expected_name,
                        "Second folder should be renamed")

    def test_project_without_product_service_tracking(self):
        """Test project creation when product doesn't have service tracking"""
        # Create product without service tracking
        simple_product = self.env['product.product'].create({
            'name': 'Simple Product',
            'type': 'consu',
            'list_price': 500.0,
        })

        # Create sale order
        sale_order = self.env['sale.order'].create({
            'partner_id': self.test_customer.id,
            'order_line': [(0, 0, {
                'product_id': simple_product.id,
                'product_uom_qty': 1,
                'price_unit': 500.0,
            })],
        })

        sale_order.action_confirm()

        # Create folder
        folder = self.env['documents.folder'].create({'name': 'Test Folder'})

        # Create project manually (since product doesn't auto-create)
        project = self.env['project.project'].create({
            'name': 'Manual Project',
            'sale_line_id': sale_order.order_line[0].id,
            'documents_folder_id': folder.id,
        })

        # Assert folder renamed correctly
        expected_name = f"{sale_order.name} - Projet - {self.test_customer.name}"
        self.assertEqual(folder.name, expected_name,
                        "Folder should be renamed even for non-service products")

    def test_folder_added_after_project_creation(self):
        """Test that folder is renamed when added after project creation via write()"""
        # Create project without folder first
        project = self.env['project.project'].create({
            'name': 'Test Project',
            'sale_line_id': self.sale_order_line.id,
        })

        # Verify no folder initially
        self.assertFalse(project.documents_folder_id,
                        "Project should have no folder initially")

        # Create folder
        folder = self.env['documents.folder'].create({'name': 'Added Later Folder'})

        # Add folder to project via write()
        project.write({'documents_folder_id': folder.id})

        # Assert folder renamed (should trigger via write override)
        expected_name = f"{self.sale_order.name} - Projet - {self.test_customer.name}"
        self.assertEqual(folder.name, expected_name,
                        "Folder should be renamed when added via write()")
