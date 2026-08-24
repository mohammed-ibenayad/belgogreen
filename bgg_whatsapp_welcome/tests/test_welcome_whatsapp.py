# -*- coding: utf-8 -*-

import logging
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'bgg_whatsapp_welcome')
class TestWelcomeWhatsapp(TransactionCase):
    """Test suite for the WhatsApp welcome message automation on project.task"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.test_customer = cls.env['res.partner'].create({
            'name': 'Test Customer For WhatsApp',
            'email': 'customer@whatsapp.test',
            'phone': '+32470000001',
        })

        cls.test_product = cls.env['product.product'].create({
            'name': 'WhatsApp Service Product',
            'type': 'service',
            'service_tracking': 'task_in_project',
            'list_price': 1000.0,
        })

        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.test_customer.id,
            'order_line': [(0, 0, {
                'product_id': cls.test_product.id,
                'product_uom_qty': 1,
                'price_unit': 1000.0,
            })],
        })
        cls.sale_order.action_confirm()

        cls.test_project = cls.env['project.project'].create({
            'name': 'Test Project For WhatsApp',
            'sale_line_id': cls.sale_order.order_line[0].id,
        })

    def _create_task(self, name, **extra):
        vals = {'name': name, 'project_id': self.test_project.id}
        vals.update(extra)
        return self.env['project.task'].create(vals)

    # ========================
    # Trigger conditions
    # ========================

    def test_welcome_task_triggers_send(self):
        """A 'Welcom call' task queues the WhatsApp welcome on creation"""
        with patch.object(type(self.env['project.task']), '_send_welcome_whatsapp',
                          return_value=(True, False)) as mock_send:
            self._create_task('Welcom call')
        mock_send.assert_called_once()

    def test_other_task_does_not_trigger_send(self):
        """Tasks with any other name never queue a WhatsApp welcome"""
        with patch.object(type(self.env['project.task']), '_send_welcome_whatsapp',
                          return_value=(True, False)) as mock_send:
            self._create_task('Other Task')
            self._create_task('Welcome call')  # correct spelling ≠ configured name
            self._create_task('welcom call')
        mock_send.assert_not_called()

    def test_disabled_by_system_parameter(self):
        """The enabled system parameter switches the automation off"""
        self.env['ir.config_parameter'].sudo().set_param(
            'bgg_whatsapp_welcome.enabled', 'False')
        with patch.object(type(self.env['project.task']), '_send_welcome_whatsapp',
                          return_value=(True, False)) as mock_send:
            self._create_task('Welcom call')
        mock_send.assert_not_called()

    def test_custom_task_name_parameter(self):
        """The task name system parameter changes which tasks trigger"""
        self.env['ir.config_parameter'].sudo().set_param(
            'bgg_whatsapp_welcome.task_name', 'Appel de bienvenue')
        with patch.object(type(self.env['project.task']), '_send_welcome_whatsapp',
                          return_value=(True, False)) as mock_send:
            self._create_task('Welcom call')
            mock_send.assert_not_called()
            self._create_task('Appel de bienvenue')
            mock_send.assert_called_once()

    def test_send_failure_does_not_block_creation(self):
        """A WhatsApp failure never blocks task creation (and thus SO confirmation)"""
        with patch.object(type(self.env['project.task']), '_send_welcome_whatsapp',
                          side_effect=Exception('Meta is down')):
            task = self._create_task('Welcom call')
        self.assertTrue(task.id, "Task must be created even when WhatsApp send explodes")
        self.assertFalse(task.welcome_whatsapp_sent)

    # ========================
    # _send_welcome_whatsapp guards
    # ========================

    def test_send_without_template_reports_error(self):
        """Without an approved template the send fails with an explanation"""
        task = self.env['project.task'].with_context(
            tracking_disable=True).create({
                'name': 'Not a welcome task',
                'project_id': self.test_project.id,
                'partner_id': self.test_customer.id,
            })
        # No template named 'belgogreen_welcome_call' exists in a fresh database
        sent, detail = task._send_welcome_whatsapp()
        self.assertFalse(sent)
        self.assertTrue(detail)
        self.assertFalse(task.welcome_whatsapp_sent)

    def test_partner_resolution_from_sale_order(self):
        """The customer falls back to the sale order partner"""
        task = self._create_task('Regular task')
        task.partner_id = False
        self.assertEqual(task._get_welcome_partner(), self.test_customer)

    def test_partner_resolution_prefers_task_partner(self):
        """An explicit task customer wins over the sale order customer"""
        other_partner = self.env['res.partner'].create({
            'name': 'Direct Task Customer',
            'phone': '+32470000002',
        })
        task = self._create_task('Regular task', partner_id=other_partner.id)
        self.assertEqual(task._get_welcome_partner(), other_partner)
