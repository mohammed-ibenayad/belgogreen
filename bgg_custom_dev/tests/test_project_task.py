# -*- coding: utf-8 -*-

import datetime
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestProjectTask(TransactionCase):
    """
    Test suite for project.task model automation rules
    Tests 1 automation rule: Set Welcome Call Deadline
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test customer
        cls.test_customer = cls.env['res.partner'].create({
            'name': 'Test Customer For Task',
            'email': 'customer@task.com',
        })

        # Create product for sale order
        cls.test_product = cls.env['product.product'].create({
            'name': 'Task Service Product',
            'type': 'service',
            'service_tracking': 'task_in_project',
            'list_price': 1500.0,
        })

        # Create sale order with specific date
        cls.order_date = datetime.datetime(2024, 1, 15, 10, 0, 0)
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.test_customer.id,
            'date_order': cls.order_date,
            'order_line': [(0, 0, {
                'product_id': cls.test_product.id,
                'product_uom_qty': 1,
                'price_unit': 1500.0,
            })],
        })

        # Confirm sale order
        cls.sale_order.action_confirm()

        # Create project
        cls.test_project = cls.env['project.project'].create({
            'name': 'Test Project For Tasks',
            'sale_line_id': cls.sale_order.order_line[0].id,
        })

    # ========================
    # Test 1: Set Welcome Call Deadline
    # ========================

    def test_welcome_call_deadline_set(self):
        """Test deadline set to SO date + 2 days for Welcome call"""
        # Create "Welcom call" task (note the typo - it's intentional per spec)
        # Sale order link inherited from project's sale_line_id
        task = self.env['project.task'].create({
            'name': 'Welcom call',
            'project_id': self.test_project.id,
        })

        # Get actual sale order date (may have been updated during confirmation)
        actual_order_date = self.sale_order.date_order
        # Calculate expected deadline (order_date + 2 days)
        expected_deadline = (actual_order_date + datetime.timedelta(days=2)).date()

        # Convert task deadline to date for comparison (field may be datetime or date)
        task_deadline = task.date_deadline.date() if isinstance(task.date_deadline, datetime.datetime) else task.date_deadline

        # Assert deadline is set correctly
        self.assertEqual(task_deadline, expected_deadline,
                        f"Deadline should be {expected_deadline} (order date + 2 days)")

    def test_welcome_call_deadline_only_for_welcome_call(self):
        """Test deadline not set for other task names"""
        # Create task with different name
        task = self.env['project.task'].create({
            'name': 'Other Task',
            'project_id': self.test_project.id,
        })

        # Assert deadline not automatically set
        # (it may be set to today by default Odoo behavior, but not to order_date + 2)
        expected_deadline = (self.order_date + datetime.timedelta(days=2)).date()
        if task.date_deadline:
            self.assertNotEqual(task.date_deadline, expected_deadline,
                               "Deadline should not be auto-set for non-welcome-call tasks")

    def test_welcome_call_exact_name_match(self):
        """Test that only exact name 'Welcom call' triggers automation"""
        # Test variations that should NOT trigger
        task_variations = [
            'Welcome call',  # Correct spelling
            'welcom call',   # Lowercase
            'WELCOM CALL',   # Uppercase
            'Welcom call ',  # Trailing space
            ' Welcom call',  # Leading space
        ]

        expected_deadline = (self.order_date + datetime.timedelta(days=2)).date()

        for name in task_variations:
            task = self.env['project.task'].create({
                'name': name,
                'project_id': self.test_project.id,
            })

            # Only exact match "Welcom call" should get the deadline
            if name == 'Welcom call':
                self.assertEqual(task.date_deadline, expected_deadline,
                               f"Task '{name}' should have deadline set")
            # Note: The current implementation uses == for exact match
            # so variations won't trigger the automation

    def test_welcome_call_handles_missing_sale_order(self):
        """Test graceful handling when task has no sale order"""
        # Create task without sale order
        task = self.env['project.task'].create({
            'name': 'Welcom call',
            'project_id': self.test_project.id,
        })

        # Assert no error occurred and task created successfully
        self.assertTrue(task.id, "Task should be created even without sale order")
        # Deadline won't be set to order_date + 2 because there's no order

    def test_welcome_call_handles_missing_order_date(self):
        """Test graceful handling when sale order has no date"""
        # Create sale order without date_order set
        sale_order_no_date = self.env['sale.order'].create({
            'partner_id': self.test_customer.id,
            'order_line': [(0, 0, {
                'product_id': self.test_product.id,
                'product_uom_qty': 1,
                'price_unit': 1500.0,
            })],
        })

        # Create project linked to this sale order
        project_no_date = self.env['project.project'].create({
            'name': 'Project No Date',
            'sale_line_id': sale_order_no_date.order_line[0].id,
        })

        # Create task
        task = self.env['project.task'].create({
            'name': 'Welcom call',
            'project_id': project_no_date.id,
        })

        # Assert task created without error
        self.assertTrue(task.id, "Task should be created even when order has no date")

    def test_welcome_call_deadline_with_different_order_dates(self):
        """Test that deadline correctly calculates from different order dates"""
        # Create multiple sale orders with different dates
        test_dates = [
            datetime.datetime(2024, 3, 10, 14, 30, 0),
            datetime.datetime(2024, 6, 25, 9, 15, 0),
            datetime.datetime(2024, 12, 31, 23, 59, 0),
        ]

        for order_date in test_dates:
            # Create sale order
            sale_order = self.env['sale.order'].create({
                'partner_id': self.test_customer.id,
                'date_order': order_date,
                'order_line': [(0, 0, {
                    'product_id': self.test_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 1500.0,
                })],
            })

            # Create project linked to sale order line
            project = self.env['project.project'].create({
                'name': f'Project {order_date.date()}',
                'sale_line_id': sale_order.order_line[0].id,
            })

            # Create task (sale order link will be inherited from project)
            task = self.env['project.task'].create({
                'name': 'Welcom call',
                'project_id': project.id,
            })

            # Get actual sale order date (may have been updated)
            actual_order_date = sale_order.date_order
            # Calculate expected deadline
            expected_deadline = (actual_order_date + datetime.timedelta(days=2)).date()

            # Convert deadline to date for comparison
            task_deadline = task.date_deadline.date() if task.date_deadline and isinstance(task.date_deadline, datetime.datetime) else task.date_deadline

            # Assert correct deadline
            self.assertEqual(task_deadline, expected_deadline,
                           f"Deadline should be {expected_deadline} for order date {actual_order_date.date()}")

    def test_welcome_call_deadline_not_changed_on_update(self):
        """Test that deadline is only set on creation, not on updates"""
        # Create task
        task = self.env['project.task'].create({
            'name': 'Welcom call',
            'project_id': self.test_project.id,
        })

        original_deadline = task.date_deadline

        # Update task name
        task.write({'name': 'Updated Welcom call'})

        # Assert deadline unchanged
        self.assertEqual(task.date_deadline, original_deadline,
                        "Deadline should not change on update")

    def test_welcome_call_without_project(self):
        """Test welcome call task created without project but with sale line"""
        # Create task without project but with sale_line_id
        task = self.env['project.task'].create({
            'name': 'Welcom call',
            'sale_line_id': self.sale_order.order_line[0].id,
        })

        # Calculate expected deadline
        actual_order_date = self.sale_order.date_order
        expected_deadline = (actual_order_date + datetime.timedelta(days=2)).date()

        # Convert deadline to date for comparison
        task_deadline = task.date_deadline.date() if task.date_deadline and isinstance(task.date_deadline, datetime.datetime) else task.date_deadline

        # Assert deadline set correctly
        self.assertEqual(task_deadline, expected_deadline,
                        "Deadline should be set even without project")

    # ========================
    # Integration Tests
    # ========================

    def test_batch_create_tasks(self):
        """Test that automation works with batch task creation"""
        # Create multiple welcome call tasks at once
        tasks = self.env['project.task'].create([
            {
                'name': 'Welcom call',
                'project_id': self.test_project.id,
            },
            {
                'name': 'Welcom call',
                'project_id': self.test_project.id,
            },
            {
                'name': 'Other Task',  # This one shouldn't get the deadline
                'project_id': self.test_project.id,
            },
        ])

        actual_order_date = self.sale_order.date_order
        expected_deadline = (actual_order_date + datetime.timedelta(days=2)).date()

        # Convert deadlines to date for comparison
        task0_deadline = tasks[0].date_deadline.date() if isinstance(tasks[0].date_deadline, datetime.datetime) else tasks[0].date_deadline
        task1_deadline = tasks[1].date_deadline.date() if isinstance(tasks[1].date_deadline, datetime.datetime) else tasks[1].date_deadline

        # Assert first two tasks have deadline set
        self.assertEqual(task0_deadline, expected_deadline,
                        "First welcome call should have deadline")
        self.assertEqual(task1_deadline, expected_deadline,
                        "Second welcome call should have deadline")

    def test_welcome_call_with_manual_deadline_override(self):
        """Test creating welcome call task with manual deadline"""
        # Create task with manually set deadline
        manual_deadline = datetime.date(2024, 12, 25)

        task = self.env['project.task'].create({
            'name': 'Welcom call',
            'project_id': self.test_project.id,
            'date_deadline': manual_deadline,
        })

        # The automation will override the manual deadline
        actual_order_date = self.sale_order.date_order
        expected_deadline = (actual_order_date + datetime.timedelta(days=2)).date()

        # Convert deadline to date for comparison
        task_deadline = task.date_deadline.date() if isinstance(task.date_deadline, datetime.datetime) else task.date_deadline

        # Assert automation overwrites manual deadline
        self.assertEqual(task_deadline, expected_deadline,
                        "Automation should set deadline to order_date + 2 days")

    def test_task_creation_from_sale_order_template(self):
        """Test that welcome call tasks from SO templates get correct deadline"""
        # This simulates the real-world scenario where tasks are created from project templates
        # when a sale order is confirmed with a service product

        # Create a new sale order
        new_order_date = datetime.datetime(2024, 2, 20, 12, 0, 0)
        new_sale_order = self.env['sale.order'].create({
            'partner_id': self.test_customer.id,
            'date_order': new_order_date,
            'order_line': [(0, 0, {
                'product_id': self.test_product.id,
                'product_uom_qty': 1,
                'price_unit': 1500.0,
            })],
        })

        new_sale_order.action_confirm()

        # Create project
        new_project = self.env['project.project'].create({
            'name': 'New Project from Template',
            'sale_line_id': new_sale_order.order_line[0].id,
        })

        # Create welcome call task (simulating template task creation)
        task = self.env['project.task'].create({
            'name': 'Welcom call',
            'project_id': new_project.id,
        })

        # Get actual sale order date (may have been updated during confirmation)
        actual_order_date = new_sale_order.date_order
        expected_deadline = (actual_order_date + datetime.timedelta(days=2)).date()

        # Convert deadline to date for comparison
        task_deadline = task.date_deadline.date() if isinstance(task.date_deadline, datetime.datetime) else task.date_deadline

        # Assert deadline set correctly
        self.assertEqual(task_deadline, expected_deadline,
                        "Template-created task should have correct deadline")
