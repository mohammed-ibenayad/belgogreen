# -*- coding: utf-8 -*-

import datetime

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

RULES_PARAM = 'bgg.admin_project_deadline_rules'
CATEGORIES_PARAM = 'bgg.admin_project_deadline_categories'
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

    def test_financement_isolation_25_calendar_days(self):
        order = self._order('Financement', 'Isolation')
        self._assert_dates(order, 25, calendar=True)

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
        self._assert_dates(order, 15, calendar=True)

    def test_payment_term_change_to_no_rule_keeps_dates(self):
        order = self._order('Paiement immédiat', 'Panneaux')
        project, _start, end = self._assert_dates(order, 10)
        order.payment_term_id = self.terms['Financement RW']
        self.assertEqual(project.date, end, "no rule: dates are left as they are")

    def test_manual_project_dates_kept_on_unrelated_order_write(self):
        order = self._order('Paiement immédiat', 'Panneaux')
        project = self._project(order)
        manual = datetime.date(2030, 1, 31)
        project.write({'date': manual})
        order.write({'note': 'unrelated change'})
        self.assertEqual(project.date, manual)

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
            '{"Paiement immédiat": {"day_type": "calendar", "panneaux": 3}}'))
        order = self._order('Paiement immédiat', 'Panneaux')
        self._assert_dates(order, 3, calendar=True)

    def test_categories_param_overrides_defaults(self):
        self.env['ir.config_parameter'].sudo().set_param(CATEGORIES_PARAM, (
            '{"panneaux": ["Accessoires"]}'))
        order = self._order('Paiement immédiat', 'Accessoires')
        self._assert_dates(order, 10)

    def test_invalid_param_falls_back_to_defaults(self):
        self.env['ir.config_parameter'].sudo().set_param(RULES_PARAM, 'not json')
        order = self._order('Paiement immédiat', 'Panneaux')
        self._assert_dates(order, 10)

    def test_payment_term_matched_case_insensitively(self):
        self.env['ir.config_parameter'].sudo().set_param(RULES_PARAM, (
            '{"PAIEMENT IMMÉDIAT": {"day_type": "business", "panneaux": 4}}'))
        order = self._order('Paiement immédiat', 'Panneaux')
        self._assert_dates(order, 4)
