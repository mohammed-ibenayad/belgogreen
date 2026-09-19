# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

RESPONSABLE_DOSSIER_GROUP = 'bgg_custom_dev.group_responsable_dossier'


@tagged('post_install', '-at_install')
class TestSaleOrderResponsableDossier(TransactionCase):
    """Dossier tab on sale.order: the Responsable must be an internal user of
    the "Responsable Dossier" group.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref(RESPONSABLE_DOSSIER_GROUP)

        cls.customer = cls.env['res.partner'].create({
            'name': 'Client Dossier',
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.customer.id,
        })

        cls.responsable = cls.env['res.users'].create({
            'name': 'Responsable Dossier User',
            'login': 'responsable.dossier@test.bgg',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group.id,
            ])],
        })
        cls.internal_user = cls.env['res.users'].create({
            'name': 'Internal User',
            'login': 'internal.user@test.bgg',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal User',
            'login': 'portal.user@test.bgg',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def test_group_exists(self):
        self.assertEqual(self.group.name, 'Responsable Dossier')

    def test_field_definition(self):
        field = self.env['sale.order']._fields['x_responsable_dossier_id']
        self.assertEqual(field.comodel_name, 'res.users')
        self.assertEqual(field.string, 'Responsable')
        self.assertTrue(field.tracking)

    def test_domain_restricts_to_group_members(self):
        domain = self.env['sale.order']._responsable_dossier_domain()
        users = self.env['res.users'].search(domain)
        self.assertIn(self.responsable, users)
        self.assertNotIn(self.internal_user, users)
        self.assertNotIn(self.portal_user, users)

    def test_assign_group_member(self):
        self.order.x_responsable_dossier_id = self.responsable
        self.assertEqual(self.order.x_responsable_dossier_id, self.responsable)

    def test_reject_internal_user_outside_group(self):
        with self.assertRaises(ValidationError):
            self.order.x_responsable_dossier_id = self.internal_user

    def test_reject_portal_user(self):
        with self.assertRaises(ValidationError):
            self.order.x_responsable_dossier_id = self.portal_user

    def test_clearing_is_allowed(self):
        self.order.x_responsable_dossier_id = self.responsable
        self.order.x_responsable_dossier_id = False
        self.assertFalse(self.order.x_responsable_dossier_id)

    # ------------------------------------------------------------------
    # Propagation to the projects / tasks of the order
    # ------------------------------------------------------------------

    @classmethod
    def _make_template_and_product(cls):
        """A project template with two tasks, and a 'project only' service
        creating a project from it on order confirmation."""
        template = cls.env['project.project'].create({
            'name': 'AMSS - Tâches Avant - Installation (test)',
            'is_template': True,
            'user_id': cls.internal_user.id,
        })
        cls.env['project.task'].create([
            {'name': 'Welcom call', 'project_id': template.id},
            {'name': 'Dossier Fluvius', 'project_id': template.id},
        ])
        product = cls.env['product.product'].create({
            'name': 'INSTALLATION BELGIQUE (test)',
            'type': 'service',
            'service_tracking': 'project_only',
            'project_template_id': template.id,
            'list_price': 100.0,
        })
        return template, product

    def _make_order(self, product, responsable=None):
        vals = {
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        }
        if responsable:
            vals['x_responsable_dossier_id'] = responsable.id
        return self.env['sale.order'].create(vals)

    def _open_tasks(self, project):
        return self.env['project.task'].search([
            ('project_id', '=', project.id),
            ('state', 'not in', ['1_done', '1_canceled']),
        ])

    def test_responsable_set_before_confirmation(self):
        """Project created on confirmation gets the Responsable as manager and
        the template tasks get them as assignee."""
        _template, product = self._make_template_and_product()
        order = self._make_order(product, responsable=self.responsable)
        order.action_confirm()

        project = order._get_dossier_projects()
        self.assertEqual(len(project), 1)
        self.assertEqual(project.user_id, self.responsable,
                         "template manager must be replaced by the Responsable")
        tasks = self._open_tasks(project)
        self.assertEqual(len(tasks), 2, "template tasks must be copied")
        for task in tasks:
            self.assertIn(self.responsable, task.user_ids)

    def test_responsable_set_after_confirmation(self):
        """Setting the Responsable on a confirmed order updates the existing
        project and its open tasks; existing assignees are kept."""
        _template, product = self._make_template_and_product()
        order = self._make_order(product)
        order.action_confirm()
        project = order._get_dossier_projects()
        self.assertEqual(project.user_id, self.internal_user,
                         "without Responsable the template manager is kept")
        task = self._open_tasks(project)[0]
        task.user_ids = [(6, 0, [self.internal_user.id])]

        order.x_responsable_dossier_id = self.responsable

        self.assertEqual(project.user_id, self.responsable)
        for t in self._open_tasks(project):
            self.assertIn(self.responsable, t.user_ids)
        self.assertIn(self.internal_user, task.user_ids,
                      "existing assignees must be kept")

    def test_responsable_change_and_clear(self):
        """Changing the Responsable swaps them on the tasks and the project;
        clearing it unassigns them from the tasks."""
        _template, product = self._make_template_and_product()
        order = self._make_order(product, responsable=self.responsable)
        order.action_confirm()
        project = order._get_dossier_projects()

        other = self.env['res.users'].create({
            'name': 'Other Responsable',
            'login': 'other.responsable@test.bgg',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id, self.group.id,
            ])],
        })
        order.x_responsable_dossier_id = other
        self.assertEqual(project.user_id, other)
        for t in self._open_tasks(project):
            self.assertIn(other, t.user_ids)
            self.assertNotIn(self.responsable, t.user_ids,
                             "the former Responsable must be unassigned")

        order.x_responsable_dossier_id = False
        for t in self._open_tasks(project):
            self.assertNotIn(other, t.user_ids)
        self.assertEqual(project.user_id, other,
                         "clearing keeps the current project manager")

    def test_new_task_in_project_gets_responsable(self):
        """A task created later in the project is assigned to the Responsable;
        a closed task is left alone when the Responsable changes."""
        _template, product = self._make_template_and_product()
        order = self._make_order(product, responsable=self.responsable)
        order.action_confirm()
        project = order._get_dossier_projects()

        new_task = self.env['project.task'].create({
            'name': 'Visite technique', 'project_id': project.id,
        })
        self.assertIn(self.responsable, new_task.user_ids)

        done_task = self.env['project.task'].create({
            'name': 'Déjà fait', 'project_id': project.id,
            'user_ids': [(6, 0, [self.internal_user.id])],
        })
        done_task.user_ids = [(6, 0, [self.internal_user.id])]
        done_task.state = '1_done'
        other = self.env['res.users'].create({
            'name': 'Other Responsable 2',
            'login': 'other.responsable2@test.bgg',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id, self.group.id,
            ])],
        })
        order.x_responsable_dossier_id = other
        self.assertNotIn(other, done_task.user_ids,
                         "closed tasks are not reassigned")
        self.assertIn(other, new_task.user_ids)

    def test_project_without_order_untouched(self):
        """Projects not linked to a sale order are never affected."""
        project = self.env['project.project'].create({
            'name': 'Interne', 'user_id': self.internal_user.id,
        })
        task = self.env['project.task'].create({
            'name': 'Tâche interne', 'project_id': project.id,
        })
        self.order.x_responsable_dossier_id = self.responsable
        self.assertEqual(project.user_id, self.internal_user)
        self.assertNotIn(self.responsable, task.user_ids)

    def _flush_tracking(self):
        """Run the precommit hooks that write mail tracking values."""
        self.env.flush_all()
        self.env.cr.precommit.run()

    def test_assignment_is_tracked_in_chatter(self):
        # mail.thread disables tracking on a record for the rest of the
        # transaction that created it, until precommit runs. The order was
        # created in setUpClass, so flush once before the tracked write.
        self._flush_tracking()
        self.order.x_responsable_dossier_id = self.responsable
        self._flush_tracking()
        tracking = self.env['mail.tracking.value'].search([
            ('mail_message_id.model', '=', 'sale.order'),
            ('mail_message_id.res_id', '=', self.order.id),
            ('field_id.name', '=', 'x_responsable_dossier_id'),
        ])
        self.assertTrue(tracking)
