# -*- coding: utf-8 -*-

import datetime

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestAmssDashboard(TransactionCase):
    """AMSS Management dashboard (Direction tab) and the "Bloqué" status of
    the admin projects. Figures are compared before / after the records a
    test creates, so data already in the database does not matter."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dashboard = cls.env['amss.management.dashboard']
        cls.customer = cls.env['res.partner'].create({'name': 'Client AMSS'})
        cls.product = cls.env['product.product'].create({
            'name': 'Panneau AMSS (test)', 'type': 'consu',
            'invoice_policy': 'order', 'list_price': 1000.0,
        })
        template = cls.env['project.project'].create({
            'name': 'Gestion Dossier Admin (test AMSS)', 'is_template': True,
        })
        cls.env['project.task'].create([
            {'name': 'Dossier Fluvius', 'project_id': template.id},
            {'name': 'Envoi Belgotest', 'project_id': template.id},
        ])
        cls.service = cls.env['product.product'].create({
            'name': 'INSTALLATION (test AMSS)', 'type': 'service',
            'service_tracking': 'project_only', 'project_template_id': template.id,
            'invoice_policy': 'order', 'list_price': 500.0,
        })

        def user(login, *groups):
            return cls.env['res.users'].create({
                'name': login, 'login': f'{login}@test.amss',
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in ('base.group_user',) + groups])],
            })
        cls.direction_user = user('direction', 'bgg_custom_dev.group_direction')
        cls.plain_user = user('plain')
        cls.responsable = user('responsable', 'project.group_project_user',
                               'bgg_custom_dev.group_responsable_dossier')
        cls.project_user = user('project_user', 'project.group_project_user')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _order(self, confirm=True, service=True, qty=1):
        lines = [(0, 0, {'product_id': self.product.id, 'product_uom_qty': qty, 'price_unit': 1000.0})]
        if service:
            lines.append((0, 0, {'product_id': self.service.id, 'product_uom_qty': 1, 'price_unit': 500.0}))
        order = self.env['sale.order'].create({'partner_id': self.customer.id, 'order_line': lines})
        if confirm:
            order.action_confirm()
        return order

    def _today_range(self):
        today = fields.Date.today()
        return today, today + datetime.timedelta(days=1)

    def _status_update(self, project, status, user=None, date=None):
        Update = self.env['project.update']
        if user:
            Update = Update.with_user(user)
        vals = {'name': 'Statut', 'project_id': project.id, 'status': status}
        if date:
            vals['date'] = date
        return Update.create(vals)

    # ------------------------------------------------------------------
    # access
    # ------------------------------------------------------------------

    def test_access_direction_group_only(self):
        with self.assertRaises(AccessError):
            self.Dashboard.with_user(self.plain_user).get_dashboard_data()
        with self.assertRaises(AccessError):
            self.Dashboard.with_user(self.plain_user).get_filter_options()
        data = self.Dashboard.with_user(self.direction_user).get_dashboard_data()
        self.assertEqual(set(data['cards']), {
            'ca_net', 'ventes_confirmees', 'tx_conversion', 'chantiers_retard', 'dossiers_bloques'})
        self.assertEqual(set(data['cash_flow']), {'signe', 'facture', 'encaisse'})

    # ------------------------------------------------------------------
    # periods
    # ------------------------------------------------------------------

    def test_previous_range(self):
        start, end = datetime.date(2026, 9, 1), datetime.date(2026, 10, 1)
        self.assertEqual(self.Dashboard._previous_range(start, end, 'month'),
                         (datetime.date(2026, 8, 1), start))
        self.assertEqual(self.Dashboard._previous_range(
            datetime.date(2026, 7, 1), datetime.date(2026, 10, 1), 'quarter'),
            (datetime.date(2026, 4, 1), datetime.date(2026, 7, 1)))
        self.assertEqual(self.Dashboard._previous_range(
            datetime.date(2026, 1, 1), datetime.date(2027, 1, 1), 'year'),
            (datetime.date(2025, 1, 1), datetime.date(2026, 1, 1)))
        self.assertEqual(self.Dashboard._previous_range(
            datetime.date(2026, 9, 10), datetime.date(2026, 9, 20), 'custom'),
            (datetime.date(2026, 8, 31), datetime.date(2026, 9, 10)))

    # ------------------------------------------------------------------
    # CA NET / Ventes Confirmées (same formulas as Suivi Commercial)
    # ------------------------------------------------------------------

    def test_sales_figures(self):
        start, end = self._today_range()
        companies = [self.env.company.id]
        before = self.Dashboard._sales_figures(start, end, companies)
        confirmed = self._order(service=False) | self._order(service=False, qty=2)
        cancelled = self._order(service=False)
        cancelled._action_cancel()
        after = self.Dashboard._sales_figures(start, end, companies)
        self.assertAlmostEqual(after['ca_net'] - before['ca_net'],
                               sum(confirmed.mapped('amount_untaxed')), places=2)
        self.assertEqual(after['ventes_confirmees'] - before['ventes_confirmees'], 2)

    def test_payment_term_filter(self):
        start, end = self._today_range()
        companies = [self.env.company.id]
        Term = self.env['account.payment.term']
        term_a = Term.create({'name': 'Condition AMSS A'})
        term_b = Term.create({'name': 'Condition AMSS B'})
        before_a = self.Dashboard._sales_figures(start, end, companies, term_a.id)
        order_a = self._order(service=False, confirm=False)
        order_a.payment_term_id = term_a
        order_a.action_confirm()
        order_b = self._order(service=False, confirm=False)
        order_b.payment_term_id = term_b
        order_b.action_confirm()
        after_a = self.Dashboard._sales_figures(start, end, companies, term_a.id)
        self.assertAlmostEqual(after_a['ca_net'] - before_a['ca_net'], order_a.amount_untaxed, places=2)
        self.assertEqual(after_a['ventes_confirmees'] - before_a['ventes_confirmees'], 1)
        # TX CONVERSION ignores the payment term (appointments have none)
        self.assertEqual(after_a['tx_conversion'],
                         self.Dashboard._sales_figures(start, end, companies)['tx_conversion'])
        cash_a = self.Dashboard._cash_flow(start, end, companies, term_a.id)
        cash_b = self.Dashboard._cash_flow(start, end, companies, term_b.id)
        self.assertGreaterEqual(cash_a['signe'], order_a.amount_untaxed)
        self.assertAlmostEqual(cash_b['signe'], order_b.amount_untaxed, places=2,
                               msg="term B only has the order created here")
        options = self.Dashboard.get_filter_options()
        self.assertIn(term_a.id, [t['id'] for t in options['payment_terms']])

    # ------------------------------------------------------------------
    # Chantiers en retard
    # ------------------------------------------------------------------

    def _dated_project(self, end):
        project = self._order()._get_dossier_projects()
        self.assertEqual(len(project), 1)
        project.sudo().write({'date_start': end - datetime.timedelta(days=10), 'date': end})
        tasks = self.env['project.task'].search([('project_id', '=', project.id)])
        tasks.sudo().write({'date_deadline': datetime.datetime.combine(end, datetime.time(15, 0))})
        return project, tasks

    def test_late_projects(self):
        today = datetime.date(2026, 10, 12)
        on_time, _tasks = self._dated_project(datetime.date(2026, 10, 20))
        replanned, tasks = self._dated_project(datetime.date(2026, 10, 20))
        tasks[:1].write({'date_deadline': datetime.datetime(2026, 10, 27, 15, 0)})
        overdue, _tasks = self._dated_project(datetime.date(2026, 10, 5))
        finished, tasks = self._dated_project(datetime.date(2026, 10, 5))
        tasks.write({'state': '1_done'})
        projects = on_time | replanned | overdue | finished
        late = self.Dashboard._late_projects(projects, today)
        self.assertEqual(late, replanned | overdue)

    # ------------------------------------------------------------------
    # "Bloqué" status and Dossiers bloqués
    # ------------------------------------------------------------------

    def test_blocked_status_set_by_responsable_dossier(self):
        project = self._order()._get_dossier_projects()
        self._status_update(project, 'blocked', user=self.responsable)
        self.assertEqual(project.last_update_status, 'blocked')
        self.assertEqual(project.last_update_color, 23)
        self.assertEqual(project.last_update_id.color, 23)
        # anyone else can neither remove it nor set it
        with self.assertRaises(AccessError):
            self._status_update(project, 'on_track', user=self.project_user)
        other = self._order()._get_dossier_projects()
        with self.assertRaises(AccessError):
            self._status_update(other, 'blocked', user=self.project_user)
        # other statuses stay free for project users
        self._status_update(other, 'at_risk', user=self.project_user)
        # the Responsable Dossier removes it
        self._status_update(project, 'on_track', user=self.responsable)
        self.assertEqual(project.last_update_status, 'on_track')

    def test_blocked_status_admin_projects_only(self):
        internal = self.env['project.project'].create({'name': 'Projet interne AMSS'})
        with self.assertRaises(ValidationError):
            self._status_update(internal, 'blocked')

    def test_blocked_count_now_and_history(self):
        project = self._order()._get_dossier_projects()
        last_month = fields.Date.today() - datetime.timedelta(days=40)
        self._status_update(project, 'blocked', date=last_month)
        self._status_update(project, 'on_track', date=fields.Date.today())
        self.assertEqual(self.Dashboard._blocked_count(project), 0, "not blocked any more")
        self.assertEqual(self.Dashboard._blocked_count(project, fields.Date.today()), 1,
                         "blocked before today")
        self.assertEqual(self.Dashboard._blocked_count(project, last_month), 0,
                         "no status before its first update")

    def test_blocked_as_of(self):
        today = fields.Date.today()
        data = self.Dashboard.get_dashboard_data()
        self.assertFalse(data['blocked_as_of'], "running period: à ce jour")
        data = self.Dashboard.get_dashboard_data(month=1, year=today.year - 1)
        self.assertEqual(data['blocked_as_of'], '31/01/%s' % (today.year - 1))

    # ------------------------------------------------------------------
    # Blocked tasks block their project
    # ------------------------------------------------------------------

    def _admin_project_and_task(self):
        project = self._order()._get_dossier_projects()
        task = self.env['project.task'].search([('project_id', '=', project.id)], limit=1)
        self.assertTrue(task)
        return project, task

    def test_blocked_task_blocks_and_unblocks_project(self):
        project, task = self._admin_project_and_task()
        self._status_update(project, 'at_risk')
        task.with_user(self.responsable).state = '05_blocked'
        self.assertEqual(project.last_update_status, 'blocked')
        self.assertTrue(project.x_blocked_by_task)
        # the project cannot leave Bloqué while the task is blocked
        with self.assertRaises(UserError):
            self._status_update(project, 'on_track', user=self.responsable)
        task.with_user(self.responsable).state = '01_in_progress'
        self.assertEqual(project.last_update_status, 'at_risk', "previous status restored")
        self.assertFalse(project.x_blocked_by_task)

    def test_closing_blocked_task_unblocks_project(self):
        project, task = self._admin_project_and_task()
        task.state = '05_blocked'
        self.assertEqual(project.last_update_status, 'blocked')
        task.state = '1_done'
        self.assertEqual(project.last_update_status, 'to_define', "no previous status: back to no status")
        self.assertFalse(project.x_blocked_by_task)
        block = self.env['project.update'].search(
            [('project_id', '=', project.id), ('status', '=', 'blocked')], limit=1)
        self.assertEqual(block.x_unblocked_on, fields.Date.today())
        tomorrow = fields.Date.today() + datetime.timedelta(days=1)
        self.assertEqual(self.Dashboard._blocked_count(project, tomorrow), 0,
                         "the block ended today")
        self.assertEqual(self.Dashboard._blocked_count(project), 0)

    def test_project_blocked_by_hand_stays_blocked(self):
        project, task = self._admin_project_and_task()
        self._status_update(project, 'blocked', user=self.responsable)
        task.state = '05_blocked'
        task.state = '01_in_progress'
        self.assertEqual(project.last_update_status, 'blocked')

    def test_blocked_task_survives_stage_change(self):
        project, task = self._admin_project_and_task()
        task.state = '05_blocked'
        stage = self.env['project.task.type'].create({'name': 'Étape AMSS', 'project_ids': [(4, project.id)]})
        task.stage_id = stage
        self.assertEqual(task.state, '05_blocked', "Odoo must not reset Bloqué on a stage change")
        self.assertEqual(project.last_update_status, 'blocked')

    def test_blocked_task_rights_and_scope(self):
        project, task = self._admin_project_and_task()
        with self.assertRaises(AccessError):
            task.with_user(self.project_user).state = '05_blocked'
        internal = self.env['project.project'].create({'name': 'Projet interne AMSS'})
        other = self.env['project.task'].create({'name': 'T', 'project_id': internal.id})
        with self.assertRaises(ValidationError):
            other.state = '05_blocked'

    # ------------------------------------------------------------------
    # Admin project Terminé from its tasks
    # ------------------------------------------------------------------

    def test_all_tasks_closed_sets_project_done(self):
        project = self._order()._get_dossier_projects()
        tasks = self.env['project.task'].search([('project_id', '=', project.id)])
        self.assertGreaterEqual(len(tasks), 2)
        self._status_update(project, 'at_risk')
        tasks[0].state = '1_done'
        self.assertEqual(project.last_update_status, 'at_risk', "one task still open")
        tasks[1:].write({'state': '1_canceled'})
        self.assertEqual(project.last_update_status, 'done')
        self.assertTrue(project.x_done_by_tasks)
        # a reopened task gives the previous status back
        tasks[0].state = '01_in_progress'
        self.assertEqual(project.last_update_status, 'at_risk')
        self.assertFalse(project.x_done_by_tasks)

    def test_done_project_without_previous_status_reopens_to_no_status(self):
        project = self._order()._get_dossier_projects()
        self.env['project.task'].search([('project_id', '=', project.id)]).write({'state': '1_done'})
        self.assertEqual(project.last_update_status, 'done')
        self.env['project.task'].create({'name': 'Nouvelle tâche', 'project_id': project.id})
        self.assertEqual(project.last_update_status, 'to_define')

    def test_project_done_by_hand_stays_done(self):
        project = self._order()._get_dossier_projects()
        self._status_update(project, 'done')
        self.env['project.task'].create({'name': 'Nouvelle tâche', 'project_id': project.id})
        self.assertEqual(project.last_update_status, 'done')

    # ------------------------------------------------------------------
    # Carnet de commandes
    # ------------------------------------------------------------------

    def _planned_order(self):
        order = self._order()
        order.x_responsable_dossier_id = self.responsable
        project = order._get_dossier_projects()
        project.sudo().write({'date_start': fields.Date.today(),
                              'date': fields.Date.today() + datetime.timedelta(days=20)})
        return order, project

    def test_order_book_rows(self):
        companies = [self.env.company.id]
        no_project = self._order(service=False)
        no_dates = self._order()
        planned, _project = self._planned_order()
        started, started_project = self._planned_order()
        self.env['project.task'].search([('project_id', '=', started_project.id)], limit=1).state = '1_done'
        blocked, blocked_project = self._planned_order()
        self._status_update(blocked_project, 'blocked')
        finished, finished_project = self._planned_order()
        self.env['project.task'].search([('project_id', '=', finished_project.id)]).write({'state': '1_done'})
        no_responsable = self._order()
        no_responsable._get_dossier_projects().sudo().write({
            'date_start': fields.Date.today(), 'date': fields.Date.today() + datetime.timedelta(days=20)})

        rows = self.Dashboard._order_book(companies)
        self.assertIn(no_project, rows['carnet_a_planifier'], "no admin project")
        self.assertIn(no_dates, rows['carnet_a_planifier'], "no deadlines")
        self.assertIn(no_responsable, rows['carnet_a_planifier'], "no Responsable")
        self.assertIn(planned, rows['carnet_planifies'])
        self.assertIn(started, rows['carnet_en_cours'])
        self.assertIn(blocked, rows['carnet_bloques'])
        for orders in rows.values():
            self.assertNotIn(finished, orders, "Terminé: out of the order book")
        figures = self.Dashboard._order_book_figures(companies)
        self.assertEqual(figures['carnet_total'], sum(len(o) for o in rows.values()))
        action = self.Dashboard.open_card('carnet_en_cours')
        self.assertIn(started.id, action['domain'][0][2])

    # ------------------------------------------------------------------
    # Métiers: CA signé par catégorie de produit
    # ------------------------------------------------------------------

    def _categ(self, path):
        """Product category for a path like 'All / Saleable / PAC' (found or
        created level by level)."""
        Categ = self.env['product.category']
        parent = Categ
        for name in [p.strip() for p in path.split('/')]:
            categ = Categ.search([('name', '=', name), ('parent_id', '=', parent.id or False)], limit=1)
            parent = categ or Categ.create({'name': name, 'parent_id': parent.id or False})
        return parent

    def _product_in(self, path):
        return self.env['product.product'].create({
            'name': 'Produit %s (test)' % path, 'type': 'consu', 'list_price': 100.0,
            'categ_id': self._categ(path).id if path else False,
        })

    def _order_with(self, *paths):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {'product_id': self._product_in(p).id, 'product_uom_qty': 1,
                                   'price_unit': 100.0}) for p in paths],
        })
        order.action_confirm()
        return order

    def test_category_metier(self):
        D = self.Dashboard
        self.assertEqual(D._category_metier(self._categ('All / Saleable / PAC')), 'Chauffage / PAC')
        self.assertEqual(D._category_metier(self._categ('All / Saleable / Boilers')), 'Chauffage / PAC')
        self.assertEqual(D._category_metier(self._categ('All / Saleable / PAC / Air-eau')), 'Chauffage / PAC')
        self.assertEqual(D._category_metier(self._categ('All / Saleable / Batteries')), 'Photovoltaïque')
        self.assertEqual(D._category_metier(self._categ('All / Saleable / Isolation')), 'Isolation')
        self.assertEqual(D._category_metier(self._categ('All / Saleable / Toiture')), 'Toiture')
        self.assertEqual(D._category_metier(self._categ('All / Saleable')), 'Autres métiers')
        self.assertEqual(D._category_metier(self._categ('All / Expenses')), 'Autres')
        self.assertEqual(D._category_metier(self.env['product.category']), 'Aucun')

    def test_order_metier(self):
        D = self.Dashboard
        pac = self._order_with('All / Saleable / PAC', 'All / Saleable / Boilers',
                               'All / Saleable / Services', 'All / Saleable / Accessoires',
                               'All / Expenses')
        self.assertEqual(D._order_metier(pac), 'Chauffage / PAC',
                         "boilers go with PAC; services, accessories, expenses do not count")
        pv = self._order_with('All / Saleable / Panneaux', 'All / Saleable / Onduleurs',
                              'All / Saleable / Batteries')
        self.assertEqual(D._order_metier(pv), 'Photovoltaïque')
        mixed = self._order_with('All / Saleable / Batteries', 'All / Saleable / PAC')
        self.assertEqual(D._order_metier(mixed), 'Mixte')
        # "Frais divers" (filed under Isolation) does not decide the métier
        frais = self._product_in('All / Saleable / Isolation')
        frais.default_code = 'FRAIS-DIV'
        softener = self._order_with('All / Saleable')
        softener.order_line = [(0, 0, {'product_id': frais.id, 'product_uom_qty': 1, 'price_unit': 50.0})]
        self.assertEqual(D._order_metier(softener), 'Autres métiers')
        services = self._order_with('All / Saleable / Services')
        self.assertEqual(D._order_metier(services), 'Services')

    def test_ca_by_metier_adds_up_to_ca_net(self):
        self._order_with('All / Saleable / PAC')
        self._order_with('All / Saleable / Panneaux', 'All / Saleable / Isolation')
        f = self.Dashboard._resolve_filters()
        rows = self.Dashboard._ca_by_metier(f)
        ca_net = self.Dashboard._sales_figures(f['date_start'], f['date_end'], f['company_ids'])['ca_net']
        self.assertAlmostEqual(sum(r['amount'] for r in rows), ca_net, places=2)
        self.assertIn('Mixte', [r['key'] for r in rows])
        action = self.Dashboard.open_card('metier:Chauffage / PAC')
        self.assertEqual(action['res_model'], 'sale.order')

    # ------------------------------------------------------------------
    # Commercial tab
    # ------------------------------------------------------------------

    def test_commercial_figures(self):
        seller = self.env['res.users'].create({
            'name': 'Vendeur AMSS', 'login': 'vendeur.amss@test.bgg',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('sales_team.group_sale_salesman').id])],
        })
        f = self.Dashboard._resolve_filters(user_id=seller.id)
        self.assertEqual(self.Dashboard._commercial_figures(f)['funnel']['bc_signes'], 0)

        def order_for(seller, cancel=False):
            order = self._order_with('All / Saleable / PAC')
            order.user_id = seller
            if cancel:
                order._action_cancel()
            return order
        confirmed = order_for(seller) | order_for(seller)
        order_for(seller, cancel=True)
        figures = self.Dashboard._commercial_figures(f)
        self.assertEqual(figures['funnel']['bc_signes'], 3, "confirmed + cancelled")
        quality = figures['qualite']
        self.assertAlmostEqual(quality['panier_moyen'],
                               sum(confirmed.mapped('amount_untaxed')) / 2, places=2)
        self.assertAlmostEqual(quality['annulation_signature'], round(100 / 3, 1), places=1)
        self.assertEqual([m['key'] for m in quality['panier_par_metier']], ['Chauffage / PAC'])
        # the seller is not in the Commercial group: counted in Autres
        autres = [b for b in figures['bc_par_commercial'] if b['key'] == 'autres']
        self.assertTrue(autres and autres[0]['count'] >= 2)
        action = self.Dashboard.open_card('funnel_bc', user_id=seller.id)
        self.assertEqual(len(action['domain'][0][2]), 3)
        # KPI cards of the Commercial tab follow the salesperson
        data = self.Dashboard.get_dashboard_data(user_id=seller.id)
        self.assertEqual(data['cards_user']['ventes_confirmees']['value'], 2)
        self.assertAlmostEqual(data['cards_user']['ca_net']['value'],
                               sum(confirmed.mapped('amount_untaxed')), places=2)
        self.assertGreaterEqual(data['cards']['ventes_confirmees']['value'], 2)
        self.assertFalse(self.Dashboard.get_dashboard_data()['cards_user'])

    # ------------------------------------------------------------------
    # Drill-down: clicking a card lists the records behind its figure
    # ------------------------------------------------------------------

    def test_open_card(self):
        order = self._order()
        project = order._get_dossier_projects()
        self._status_update(project, 'blocked')
        action = self.Dashboard.open_card('ventes_confirmees')
        self.assertEqual(action['res_model'], 'sale.order')
        self.assertIn(order.id, action['domain'][0][2])
        action = self.Dashboard.open_card('dossiers_bloques')
        self.assertEqual(action['res_model'], 'project.project')
        self.assertIn(project.id, action['domain'][0][2])
        self.assertTrue(action['name'].endswith('à ce jour'))
        # a project without a company of its own is matched through its order
        project.sudo().company_id = False
        self.assertIn(project, self.Dashboard._admin_projects([order.company_id.id]))
        self.assertEqual(self.Dashboard.open_card('facture')['res_model'], 'account.move')
        with self.assertRaises(AccessError):
            self.Dashboard.with_user(self.plain_user).open_card('ca_net')

    # ------------------------------------------------------------------
    # CA signé / facturé / encaissé
    # ------------------------------------------------------------------

    def test_cash_flow(self):
        start, end = self._today_range()
        companies = [self.env.company.id]
        journal = self.env['account.journal'].search([
            ('type', 'in', ('bank', 'cash')), ('company_id', '=', self.env.company.id)], limit=1)
        if not journal:
            self.skipTest("no bank or cash journal to register a payment")
        before = self.Dashboard._cash_flow(start, end, companies)
        order = self._order(service=False, qty=2)
        invoice = order._create_invoices()
        invoice.action_post()
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'amount': invoice.amount_total / 2, 'journal_id': journal.id})._create_payments()
        after = self.Dashboard._cash_flow(start, end, companies)
        self.assertAlmostEqual(after['signe'] - before['signe'], order.amount_untaxed, places=2)
        self.assertAlmostEqual(after['facture'] - before['facture'], invoice.amount_untaxed, places=2)
        self.assertAlmostEqual(after['encaisse'] - before['encaisse'], invoice.amount_untaxed / 2, places=2)

        # a full credit note cancels the invoiced and the collected amounts
        refund = invoice._reverse_moves()
        refund.action_post()
        final = self.Dashboard._cash_flow(start, end, companies)
        self.assertAlmostEqual(final['facture'] - before['facture'], 0, places=2)
