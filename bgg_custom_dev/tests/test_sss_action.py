# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.bgg_custom_dev.models.sale_order_sss import SSS_ACTION_NAME

MANAGER_PARAM = 'bgg.sss_project_manager_login'


@tagged('post_install', '-at_install')
class TestCreateSssTasks(TransactionCase):
    """'Créer tâches SSS' (ported server action): SSS project, stages and
    tasks for confirmed and paid orders; project manager from the system
    parameter."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        if not company.chart_template:
            cls.env['account.chart_template'].try_loading(
                'generic_coa', company=company, install_demo=False)

        cls.customer = cls.env['res.partner'].create({
            'name': 'Client SSS', 'street': '1 rue du Test', 'zip': '1000',
            'city': 'Bruxelles', 'country_id': cls.env.ref('base.be').id,
            'phone': '+32 2 000 00 00',
        })
        cls.manager = cls.env['res.users'].create({
            'name': 'Chef SSS', 'login': 'chef.sss@test.bgg',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.env['ir.config_parameter'].sudo().set_param(MANAGER_PARAM, cls.manager.login)

        Categ = cls.env['product.category']
        # "All / Saleable" is legacy data on the production database (Odoo 19
        # ships "Goods" and "Services" as root categories): build it by name.
        saleable = Categ.search([('complete_name', '=', 'All / Saleable')], limit=1)
        if not saleable:
            root = (Categ.search([('name', '=', 'All'), ('parent_id', '=', False)], limit=1)
                    or Categ.create({'name': 'All'}))
            saleable = Categ.create({'name': 'Saleable', 'parent_id': root.id})
        panneaux = Categ.create({'name': 'Panneaux (SSS test)', 'parent_id': saleable.id})
        cls.panel = cls.env['product.product'].create({
            'name': 'Panneau 400W (SSS test)', 'type': 'consu', 'invoice_policy': 'order',
            'categ_id': panneaux.id, 'list_price': 100.0,
        })
        cls.inverter = cls.env['product.product'].create({
            'name': 'Onduleur 5kW (SSS test)', 'type': 'consu', 'invoice_policy': 'order',
            'categ_id': panneaux.id, 'list_price': 500.0,
        })
        cls.service = cls.env['product.product'].create({
            'name': 'Installation (SSS test)', 'type': 'service', 'invoice_policy': 'order',
            'categ_id': saleable.id, 'list_price': 50.0,
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _order(self, products, confirm=True):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {'product_id': p.id, 'product_uom_qty': 2,
                                   'price_unit': p.list_price}) for p in products],
        })
        if confirm:
            order.action_confirm()
        return order

    def _invoice(self, order, pay=True):
        invoices = order._create_invoices()
        invoices.action_post()
        if pay:
            wizard = self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=invoices.ids).create({})
            wizard.action_create_payments()
            self.assertIn(invoices.payment_state, ('paid', 'in_payment', 'partial'))
        return invoices

    def _project(self, order):
        return self.env['project.project'].search([
            ('name', '=', f"{order.name} - SSS - {self.customer.name}")])

    def _tasks(self, project):
        return self.env['project.task'].search([('project_id', '=', project.id)])

    def _assert_no_error_logged(self):
        errors = self.env['ir.logging'].search([
            ('func', '=', SSS_ACTION_NAME), ('level', '=', 'error')])
        self.assertFalse(errors, "action logged an error: %s" % errors.mapped('message'))

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_no_selection(self):
        self.env['sale.order'].browse().action_create_sss_tasks()
        self._assert_no_error_logged()

    def test_quotation_skipped(self):
        order = self._order([self.panel], confirm=False)
        order.action_create_sss_tasks()
        self.assertFalse(self._project(order))
        self._assert_no_error_logged()

    def test_unpaid_order_skipped(self):
        order = self._order([self.panel])
        self._invoice(order, pay=False)
        order.action_create_sss_tasks()
        self.assertFalse(self._project(order))
        self._assert_no_error_logged()

    def test_paid_order_creates_project_stages_tasks(self):
        order = self._order([self.panel, self.inverter, self.service])
        self._invoice(order)
        order.action_create_sss_tasks()
        self._assert_no_error_logged()

        project = self._project(order)
        self.assertEqual(len(project), 1)
        self.assertEqual(project.user_id, self.manager,
                         "the SSS project manager comes from the system parameter")
        self.assertEqual(project.partner_id, self.customer)
        if 'is_fsm' in project._fields:
            self.assertTrue(project.is_fsm)
        self.assertEqual(project.label_tasks, 'Tâches - Service sur Site')

        # The field service app adds its own default stages to a new FSM
        # project; the action adds these two on top of them.
        stages = self.env['project.task.type'].search([('project_ids', 'in', project.id)])
        self.assertTrue({'FSM: ToDo', 'FSM: In progress/Done'} <= set(stages.mapped('name')),
                        "action stages missing among %s" % stages.mapped('name'))

        tasks = self._tasks(project)
        self.assertEqual(sorted(tasks.mapped('name')), sorted([self.panel.name, self.inverter.name]),
                         "one task per consumable line, none for the service")
        for task in tasks:
            self.assertEqual(task.sale_order_id, order)
            self.assertEqual(task.partner_id, self.customer)
            self.assertFalse(task.user_ids, "tasks are left unassigned")
            self.assertEqual(task.stage_id.name, 'FSM: ToDo')
            self.assertEqual(task.allocated_hours, 2)

    def test_rerun_creates_nothing_more(self):
        order = self._order([self.panel])
        self._invoice(order)
        order.action_create_sss_tasks()
        project = self._project(order)
        n_tasks = len(self._tasks(project))
        order.action_create_sss_tasks()
        self.assertEqual(len(self._project(order)), 1)
        self.assertEqual(len(self._tasks(project)), n_tasks)
        self._assert_no_error_logged()

    def test_manager_param_missing_leaves_manager_empty(self):
        self.env['ir.config_parameter'].sudo().set_param(MANAGER_PARAM, False)
        order = self._order([self.panel])
        self._invoice(order)
        order.action_create_sss_tasks()
        self._assert_no_error_logged()
        self.assertFalse(self._project(order).user_id)

    def test_existing_sss_project_untouched(self):
        other = self._order([self.panel])
        self._invoice(other)
        self.env['ir.config_parameter'].sudo().set_param(MANAGER_PARAM, False)
        other.action_create_sss_tasks()
        existing = self._project(other)
        self.assertFalse(existing.user_id)
        # parameter set afterwards: only projects created from now on get it
        self.env['ir.config_parameter'].sudo().set_param(MANAGER_PARAM, self.manager.login)
        order = self._order([self.inverter])
        self._invoice(order)
        order.action_create_sss_tasks()
        self._assert_no_error_logged()
        self.assertEqual(self._project(order).user_id, self.manager)
        self.assertFalse(existing.user_id, "existing SSS projects are not changed")
