# -*- coding: utf-8 -*-

import datetime

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

RULES_PARAM = 'bgg.admin_project_deadline_rules'
BGG_TZ = 'Europe/Brussels'


@tagged('post_install', '-at_install')
class TestAdminProjectDeadlines(TransactionCase):
    """Admin project deadlines (Dossier): project start = order confirmation
    date, project end = start + delay from the payment term x product
    category rules, task deadlines = project end date."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env['res.partner'].create({'name': 'Client Délais'})

        # Payment terms exist in production with these names; resolve or create.
        Term = cls.env['account.payment.term']
        cls.terms = {}
        for name in ('Paiement immédiat', 'Financement', 'Financement RW'):
            cls.terms[name] = (Term.search([('name', '=ilike', name)], limit=1)
                               or Term.create({'name': name}))

        # Product categories as in production (name matching, parents allowed).
        Categ = cls.env['product.category']
        saleable = Categ.create({'name': 'Saleable (test)'})
        cls.categs = {
            name: Categ.create({'name': name, 'parent_id': saleable.id})
            for name in ('Panneaux', 'Onduleurs', 'Batteries', 'PAC', 'Isolation', 'Accessoires')
        }
        cls.products = {
            name: cls.env['product.product'].create({
                'name': f'{name} (test)', 'type': 'consu',
                'categ_id': categ.id, 'list_price': 10.0,
            })
            for name, categ in cls.categs.items()
        }

        # Project template + "project only" service creating the admin project.
        cls.template = cls.env['project.project'].create({
            'name': 'AMSS - Tâches Avant - Installation (test)',
            'is_template': True,
        })
        cls.env['project.task'].create([
            {'name': 'Welcom call', 'project_id': cls.template.id},
            {'name': 'Dossier Fluvius', 'project_id': cls.template.id},
        ])
        cls.service = cls.env['product.product'].create({
            'name': 'INSTALLATION BELGIQUE (test)',
            'type': 'service',
            'service_tracking': 'project_only',
            'project_template_id': cls.template.id,
            'list_price': 100.0,
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _order(self, term_name, *product_names, confirm=True):
        lines = [(0, 0, {'product_id': self.service.id, 'product_uom_qty': 1, 'price_unit': 100.0})]
        lines += [(0, 0, {'product_id': self.products[n].id, 'product_uom_qty': 1, 'price_unit': 10.0})
                  for n in product_names]
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'payment_term_id': self.terms[term_name].id,
            'order_line': lines,
        })
        if confirm:
            order.action_confirm()
        return order

    def _project(self, order):
        project = order._get_dossier_projects()
        self.assertEqual(len(project), 1, "one admin project per order")
        return project

    def _open_tasks(self, project):
        return self.env['project.task'].search([
            ('project_id', '=', project.id),
            ('state', 'not in', ['1_done', '1_canceled']),
        ])

    def _deadline_date(self, task):
        self.assertTrue(task.date_deadline, "task must have a deadline")
        return fields.Datetime.context_timestamp(
            task.with_context(tz=BGG_TZ), task.date_deadline).date()

    def _assert_dates(self, order, expected_days, calendar=False):
        project = self._project(order)
        start = order._admin_deadline_start_date()
        self.assertEqual(project.date_start, start,
                         "project start must be the confirmation date")
        if calendar:
            end = start + datetime.timedelta(days=expected_days)
        else:
            end = order._add_business_days(start, expected_days)
        self.assertEqual(project.date, end)
        tasks = self._open_tasks(project)
        self.assertEqual(len(tasks), 2, "template tasks must be copied")
        for task in tasks:
            self.assertEqual(self._deadline_date(task), end,
                             "task deadline must be the project end date")
        return project, start, end

    # ------------------------------------------------------------------
    # business days
    # ------------------------------------------------------------------

    def test_add_business_days(self):
        SaleOrder = self.env['sale.order']
        friday = datetime.date(2026, 9, 18)
        self.assertEqual(SaleOrder._add_business_days(friday, 0), friday)
        self.assertEqual(SaleOrder._add_business_days(friday, 1), datetime.date(2026, 9, 21))
        self.assertEqual(SaleOrder._add_business_days(friday, 10), datetime.date(2026, 10, 2))
        saturday = datetime.date(2026, 9, 19)
        self.assertEqual(SaleOrder._add_business_days(saturday, 1), datetime.date(2026, 9, 21))
        self.assertEqual(SaleOrder._add_business_days(saturday, 5), datetime.date(2026, 9, 25))

    # ------------------------------------------------------------------
    # rules
    # ------------------------------------------------------------------

    def test_immediate_panels_10_business_days(self):
        order = self._order('Paiement immédiat', 'Panneaux', 'Onduleurs')
        self._assert_dates(order, 10)

    def test_longest_delay_wins(self):
        order = self._order('Paiement immédiat', 'Panneaux', 'PAC')
        self._assert_dates(order, 15)
        order = self._order('Paiement immédiat', 'Batteries', 'Isolation', 'PAC')
        self._assert_dates(order, 20)

    def test_financement_isolation_25_business_days(self):
        order = self._order('Financement', 'Isolation')
        self._assert_dates(order, 25)

    def test_financement_rw_has_no_rule(self):
        order = self._order('Financement RW', 'Panneaux')
        project = self._project(order)
        self.assertFalse(project.date_start)
        self.assertFalse(project.date)
        for task in self._open_tasks(project):
            self.assertFalse(task.date_deadline)

    def test_no_mapped_category_no_dates(self):
        order = self._order('Paiement immédiat', 'Accessoires')
        project = self._project(order)
        self.assertFalse(project.date_start)
        self.assertFalse(project.date)

    def test_no_payment_term_no_dates(self):
        order = self._order('Paiement immédiat', 'Panneaux', confirm=False)
        order.payment_term_id = False
        order.action_confirm()
        project = self._project(order)
        self.assertFalse(project.date)

    # ------------------------------------------------------------------
    # recomputation and manual edits
    # ------------------------------------------------------------------

    def test_payment_term_change_recomputes(self):
        order = self._order('Paiement immédiat', 'Panneaux')
        self._assert_dates(order, 10)
        order.payment_term_id = self.terms['Financement']
        self._assert_dates(order, 15)

    def test_payment_term_change_to_no_rule_keeps_dates(self):
        order = self._order('Paiement immédiat', 'Panneaux')
        project, _start, end = self._assert_dates(order, 10)
        order.payment_term_id = self.terms['Financement RW']
        self.assertEqual(project.date, end, "no rule: dates are left as they are")

    def test_unrelated_order_write_keeps_dates(self):
        order = self._order('Paiement immédiat', 'Panneaux')
        project, _start, end = self._assert_dates(order, 10)
        order.write({'note': 'unrelated change'})
        self.assertEqual(project.date, end)

    # ------------------------------------------------------------------
    # form warning: installation product missing
    # ------------------------------------------------------------------

    def _order_without_service(self, *product_names):
        return self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'payment_term_id': self.terms['Paiement immédiat'].id,
            'order_line': [(0, 0, {'product_id': self.products[n].id,
                                   'product_uom_qty': 1, 'price_unit': 10.0})
                           for n in product_names],
        })

    def test_installation_product_missing_flag(self):
        # hardware without the installation service: missing
        order = self._order_without_service('Panneaux', 'Onduleurs')
        self.assertTrue(order.x_installation_product_missing)
        # still missing once confirmed without a project
        order.action_confirm()
        self.assertFalse(order._get_dossier_projects())
        self.assertTrue(order.x_installation_product_missing)
        # hardware with the installation service: not missing
        order = self._order('Paiement immédiat', 'Panneaux', confirm=False)
        self.assertFalse(order.x_installation_product_missing)
        order.action_confirm()
        self.assertFalse(order.x_installation_product_missing)
        # no hardware at all: nothing to warn about
        order = self._order_without_service('Accessoires')
        self.assertFalse(order.x_installation_product_missing)

    # ------------------------------------------------------------------
    # locked fields on admin projects
    # ------------------------------------------------------------------

    def test_admin_project_locked_fields(self):
        order = self._order('Paiement immédiat', 'Panneaux')
        project, start, end = self._assert_dates(order, 10)
        self.assertTrue(project.x_is_admin_dossier_project)
        # The test environment runs as the superuser, which counts as sudo
        # (the automations' path). Write as a regular project manager, the
        # way a user editing the form does.
        manager = self.env['res.users'].create({
            'name': 'Chef de projet test', 'login': 'chef.projet@test.bgg',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('project.group_project_manager').id,
            ])],
        })
        other_user = self.env['res.users'].create({
            'name': 'Autre chef', 'login': 'autre.chef@test.bgg',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        as_manager = project.with_user(manager)
        # Other fields stay editable (also proves the user has write access,
        # so the errors below are the lock, not an access error).
        as_manager.write({'name': 'Renommé'})
        self.assertEqual(project.name, 'Renommé')
        # Re-sending the current values (as the form does) is not a change.
        as_manager.write({'user_id': project.user_id.id, 'date_start': start, 'date': end})
        with self.assertRaises(UserError):
            as_manager.write({'user_id': other_user.id})
        with self.assertRaises(UserError):
            as_manager.write({'date_start': start + datetime.timedelta(days=1)})
        with self.assertRaises(UserError):
            as_manager.write({'date': datetime.date(2030, 1, 31)})
        self.assertNotEqual(project.user_id, other_user)
        self.assertEqual(project.date_start, start)
        self.assertEqual(project.date, end)

    def test_automation_still_writes_locked_fields(self):
        """The order-driven recomputation (sudo) is not blocked."""
        order = self._order('Paiement immédiat', 'Panneaux')
        order.payment_term_id = self.terms['Financement']
        self._assert_dates(order, 15)

    def test_project_without_order_not_locked(self):
        project = self.env['project.project'].create({'name': 'Interne'})
        self.assertFalse(project.x_is_admin_dossier_project)
        project.write({'date_start': datetime.date(2030, 1, 1),
                       'date': datetime.date(2030, 1, 31)})
        self.assertEqual(project.date, datetime.date(2030, 1, 31))

    def test_new_task_gets_project_end_deadline(self):
        order = self._order('Paiement immédiat', 'Panneaux')
        project, _start, end = self._assert_dates(order, 10)
        task = self.env['project.task'].create({
            'name': 'Visite technique', 'project_id': project.id,
        })
        self.assertEqual(self._deadline_date(task), end)

    def test_closed_task_not_updated(self):
        order = self._order('Paiement immédiat', 'Panneaux')
        project, _start, end = self._assert_dates(order, 10)
        done = self._open_tasks(project)[0]
        done.state = '1_done'
        order.payment_term_id = self.terms['Financement']
        self.assertEqual(self._deadline_date(done), end,
                         "closed tasks keep their deadline")

    def test_project_without_order_untouched(self):
        project = self.env['project.project'].create({'name': 'Interne'})
        task = self.env['project.task'].create({'name': 'T', 'project_id': project.id})
        self.assertFalse(project.date)
        self.assertFalse(task.date_deadline)

    # ------------------------------------------------------------------
    # system parameters
    # ------------------------------------------------------------------

    def test_rules_param_overrides_defaults(self):
        self.env['ir.config_parameter'].sudo().set_param(RULES_PARAM, (
            '{"Paiement immédiat": {"day_type": "calendar", "Panneaux": 3}}'))
        order = self._order('Paiement immédiat', 'Panneaux')
        self._assert_dates(order, 3, calendar=True)

    def test_new_category_added_by_param(self):
        self.env['ir.config_parameter'].sudo().set_param(RULES_PARAM, (
            '{"Paiement immédiat": {"day_type": "business", "Accessoires": 7}}'))
        order = self._order('Paiement immédiat', 'Accessoires')
        self._assert_dates(order, 7)

    def test_invalid_param_falls_back_to_defaults(self):
        self.env['ir.config_parameter'].sudo().set_param(RULES_PARAM, 'not json')
        order = self._order('Paiement immédiat', 'Panneaux')
        self._assert_dates(order, 10)

    def test_names_matched_case_insensitively(self):
        self.env['ir.config_parameter'].sudo().set_param(RULES_PARAM, (
            '{"PAIEMENT IMMÉDIAT": {"day_type": "business", "panneaux": 4}}'))
        order = self._order('Paiement immédiat', 'Panneaux')
        self._assert_dates(order, 4)

    def test_category_matched_through_parent(self):
        child = self.env['product.category'].create({
            'name': 'Panneaux bifaciaux', 'parent_id': self.categs['Panneaux'].id,
        })
        product = self.env['product.product'].create({
            'name': 'Panneau bifacial (test)', 'type': 'consu',
            'categ_id': child.id, 'list_price': 10.0,
        })
        order = self._order('Paiement immédiat', confirm=False)
        order.write({'order_line': [(0, 0, {
            'product_id': product.id, 'product_uom_qty': 1, 'price_unit': 10.0,
        })]})
        order.action_confirm()
        self._assert_dates(order, 10)

    # ------------------------------------------------------------------
    # admin tasks following the SSS reference dates
    # ------------------------------------------------------------------

    SSS_TASKS = {
        'Réclamation du solde': 0,
        'Création des commissions': 0,
        'Chargement schéma unifilaire': 5,
        'Envoi Belgotest + coordonnées RESA / ORES': 10,
    }

    def _make_sss_template_product(self, task_names=None):
        """A second template holding the SSS-driven admin tasks plus a plain
        task, and its 'project only' service."""
        template = self.env['project.project'].create({
            'name': 'Gestion Dossier Admin (test SSS)', 'is_template': True,
        })
        names = list(task_names or self.SSS_TASKS) + ['Welcom call']
        self.env['project.task'].create([
            {'name': n, 'project_id': template.id} for n in names])
        return self.env['product.product'].create({
            'name': 'INSTALLATION (test SSS)', 'type': 'service',
            'service_tracking': 'project_only',
            'project_template_id': template.id, 'list_price': 100.0,
        })

    def _order_sss(self, term_name, *product_names, service=None):
        service = service or self._make_sss_template_product()
        lines = [(0, 0, {'product_id': service.id, 'product_uom_qty': 1, 'price_unit': 100.0})]
        lines += [(0, 0, {'product_id': self.products[n].id, 'product_uom_qty': 1, 'price_unit': 10.0})
                  for n in product_names]
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'payment_term_id': self.terms[term_name].id,
            'order_line': lines,
        })
        order.action_confirm()
        return order

    def _task(self, project, name):
        task = self.env['project.task'].search([
            ('project_id', '=', project.id), ('name', '=', name)], limit=1)
        self.assertTrue(task, "task %r must exist in the project" % name)
        return task

    def _planned_start_date(self, task):
        if 'planned_date_begin' not in task._fields:
            return None
        self.assertTrue(task.planned_date_begin)
        return fields.Datetime.context_timestamp(
            task.with_context(tz=BGG_TZ), task.planned_date_begin).date()

    def _assert_sss_tasks(self, order, sss_start_offset, sss_days, admin_days):
        project = self._project(order)
        bc = order._admin_deadline_start_date()
        add = order._add_business_days
        sss_start = add(bc, sss_start_offset)
        sss_end = add(sss_start, sss_days)
        self.assertEqual(order._compute_sss_reference_dates(), (sss_start, sss_end))
        for name, offset in self.SSS_TASKS.items():
            task = self._task(project, name)
            self.assertEqual(self._deadline_date(task), add(sss_end, offset),
                             "deadline of %r" % name)
            start = self._planned_start_date(task)
            if start is not None:
                self.assertEqual(start, sss_end, "planned start of %r" % name)
        # a task outside the rules keeps the admin project end date
        other = self._task(project, 'Welcom call')
        self.assertEqual(self._deadline_date(other), add(bc, admin_days))
        self.assertEqual(project.date, add(bc, admin_days))
        return project, sss_end

    def test_sss_tasks_immediate_panels(self):
        order = self._order_sss('Paiement immédiat', 'Panneaux', 'Onduleurs')
        self._assert_sss_tasks(order, sss_start_offset=5, sss_days=5, admin_days=10)

    def test_sss_tasks_financing_pac_longest_wins(self):
        order = self._order_sss('Financement', 'Panneaux', 'PAC')
        self._assert_sss_tasks(order, sss_start_offset=10, sss_days=30, admin_days=20)

    def test_sss_tasks_recomputed_on_term_change(self):
        order = self._order_sss('Paiement immédiat', 'Isolation')
        self._assert_sss_tasks(order, sss_start_offset=5, sss_days=15, admin_days=20)
        order.payment_term_id = self.terms['Financement']
        self._assert_sss_tasks(order, sss_start_offset=10, sss_days=35, admin_days=25)

    def test_sss_task_names_matched_loosely(self):
        service = self._make_sss_template_product(task_names=[
            'reclamation du solde', '  CRÉATION  DES COMMISSIONS ',
            'Chargement schema unifilaire', 'envoi belgotest + coordonnees resa / ores',
        ])
        order = self._order_sss('Paiement immédiat', 'Panneaux', service=service)
        project = self._project(order)
        bc = order._admin_deadline_start_date()
        sss_end = order._add_business_days(order._add_business_days(bc, 5), 5)
        self.assertEqual(self._deadline_date(self._task(project, 'reclamation du solde')), sss_end)
        self.assertEqual(self._deadline_date(self._task(project, 'Chargement schema unifilaire')),
                         order._add_business_days(sss_end, 5))
        self.assertEqual(
            self._deadline_date(self._task(project, 'envoi belgotest + coordonnees resa / ores')),
            order._add_business_days(sss_end, 10))

    def test_sss_task_created_later_gets_its_dates(self):
        order = self._order_sss('Paiement immédiat', 'Panneaux')
        project, sss_end = self._assert_sss_tasks(order, sss_start_offset=5, sss_days=5, admin_days=10)
        task = self.env['project.task'].create({
            'name': 'Chargement schéma unifilaire (bis)', 'project_id': project.id,
        })
        self.assertEqual(self._deadline_date(task), project.date,
                         "a name outside the rules gets the project end date")
        task = self.env['project.task'].create({
            'name': 'Chargement schéma unifilaire', 'project_id': project.id,
        })
        self.assertEqual(self._deadline_date(task), order._add_business_days(sss_end, 5))

    def test_sss_no_rule_no_task_dates(self):
        order = self._order_sss('Financement RW', 'Panneaux')
        self.assertIsNone(order._compute_sss_reference_dates())
        self.assertEqual(order._compute_admin_task_dates(), {})
        project = self._project(order)
        for name in self.SSS_TASKS:
            self.assertFalse(self._task(project, name).date_deadline)

    def test_task_rules_param_overrides_defaults(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'bgg.admin_task_deadline_rules',
            '{"day_type": "business", "tasks": {"Réclamation du solde": 3}}')
        order = self._order_sss('Paiement immédiat', 'Panneaux')
        project = self._project(order)
        bc = order._admin_deadline_start_date()
        sss_end = order._add_business_days(order._add_business_days(bc, 5), 5)
        self.assertEqual(self._deadline_date(self._task(project, 'Réclamation du solde')),
                         order._add_business_days(sss_end, 3))
        # no longer listed: back to the project end date
        self.assertEqual(self._deadline_date(self._task(project, 'Création des commissions')),
                         project.date)
