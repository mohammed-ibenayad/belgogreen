# -*- coding: utf-8 -*-

import datetime

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestStudioFields(TransactionCase):
    """Former Odoo Studio fields, now declared by the module."""

    def test_fields_owned_by_module(self):
        for model, name in (('sale.order', 'x_studio_organisateur_du_rendez_vous'),
                            ('sale.order', 'x_studio_restant_a_facturer'),
                            ('sale.order', 'x_studio_vendeur_associes'),
                            ('calendar.event', 'x_studio_monetary_field_gq_1k2nflo0n')):
            field = self.env['ir.model.fields']._get(model, name)
            self.assertEqual(field.state, 'base', name)
            self.assertIn('bgg_custom_dev', field._get_external_ids()[field.id][0], name)

    def test_vendeur_associes_link_table(self):
        field = self.env['sale.order']._fields['x_studio_vendeur_associes']
        self.assertEqual((field.relation, field.column1, field.column2),
                         ('x_res_users_sale_order_rel', 'sale_order_id', 'res_users_id'))

    def test_organisateur_from_opportunity_event(self):
        organizer = self.env['res.users'].create({
            'name': 'Organisateur RDV', 'login': 'organisateur_rdv',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('sales_team.group_sale_salesman_all_leads').id])],
        })
        partner = self.env['res.partner'].create({'name': 'Client Organisateur'})
        lead = self.env['crm.lead'].create({'name': 'Opportunité', 'partner_id': partner.id, 'type': 'opportunity'})
        now = fields.Datetime.now()
        self.env['calendar.event'].with_user(organizer).create({
            'name': 'RDV', 'start': now, 'stop': now + datetime.timedelta(hours=1),
            'opportunity_id': lead.id,
        })
        order = self.env['sale.order'].create({'partner_id': partner.id, 'opportunity_id': lead.id})
        self.assertEqual(order.x_studio_organisateur_du_rendez_vous, organizer)


@tagged('post_install', '-at_install')
class TestCreateSssTasks(TransactionCase):
    """"Créer tâches SSS": plain project flagged SSS, one task per product to
    install, for confirmed and (partly) paid orders only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Categ = cls.env['product.category']
        all_categ = Categ.search([('complete_name', '=', 'All')], limit=1) or Categ.create({'name': 'All'})
        saleable = (Categ.search([('complete_name', '=', 'All / Saleable')], limit=1)
                    or Categ.create({'name': 'Saleable', 'parent_id': all_categ.id}))
        panels = Categ.create({'name': 'Panneaux (test SSS)', 'parent_id': saleable.id})
        other = Categ.create({'name': 'Hors installation (test SSS)', 'parent_id': all_categ.id})
        cls.panel = cls.env['product.product'].create({
            'name': 'Panneau 400W', 'type': 'consu', 'categ_id': panels.id,
            'invoice_policy': 'order', 'list_price': 100.0,
        })
        cls.inverter = cls.env['product.product'].create({
            'name': 'Onduleur', 'type': 'consu', 'categ_id': saleable.id,
            'invoice_policy': 'order', 'list_price': 100.0,
        })
        cls.brochure = cls.env['product.product'].create({
            'name': 'Brochure', 'type': 'consu', 'categ_id': other.id,
            'invoice_policy': 'order', 'list_price': 1.0,
        })
        cls.customer = cls.env['res.partner'].create({'name': 'Client SSS'})
        cls.manager = cls.env['res.users'].create({
            'name': 'Chef SSS', 'login': 'chef_sss', 'email': 'chef.sss@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('project.group_project_user').id])],
        })
        cls.env['ir.config_parameter'].sudo().set_param('bgg.sss_project_manager_login', 'Chef.SSS@example.com')
        cls.journal = cls.env['account.journal'].search([
            ('type', 'in', ('bank', 'cash')), ('company_id', '=', cls.env.company.id)], limit=1)

    def _order(self, confirm=True):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [
                (0, 0, {'product_id': self.panel.id, 'product_uom_qty': 12, 'price_unit': 100.0}),
                (0, 0, {'product_id': self.inverter.id, 'product_uom_qty': 1.5, 'price_unit': 100.0}),
                (0, 0, {'product_id': self.brochure.id, 'product_uom_qty': 1, 'price_unit': 1.0}),
            ],
        })
        if confirm:
            order.action_confirm()
        return order

    def _pay(self, order, ratio=1.0):
        if not self.journal:
            self.skipTest("no bank or cash journal to register a payment")
        invoice = order._create_invoices()
        invoice.action_post()
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'amount': invoice.amount_total * ratio, 'journal_id': self.journal.id})._create_payments()
        return invoice

    def test_unpaid_or_draft_orders_are_skipped(self):
        draft = self._order(confirm=False)
        unpaid = self._order()
        result = (draft | unpaid).action_create_sss_tasks()
        self.assertEqual(result['params']['title'], 'Aucune commande valide')
        self.assertFalse(self.env['project.project'].search([('x_sss_sale_order_id', 'in', (draft | unpaid).ids)]))

    def test_paid_order_gets_project_and_tasks(self):
        order = self._order()
        self._pay(order, ratio=0.5)
        result = order.action_create_sss_tasks()
        self.assertEqual(result['params']['type'], 'success')
        self.assertIn('1 projet(s) SSS créé(s) - 2 tâche(s) SSS créée(s)', result['params']['message'])

        project = order._get_sss_project()
        self.assertTrue(project.x_is_sss_project)
        self.assertEqual(project.x_sss_sale_order_id, order)
        self.assertEqual(project.name, f"{order.name} - SSS - Client SSS")
        self.assertEqual(project.user_id, self.manager)
        self.assertEqual(project.privacy_visibility, 'employees')
        self.assertEqual(project.type_ids.sorted('sequence').mapped('name'),
                         ['SSS: À faire', 'SSS: Encours/Fait'])
        self.assertFalse(project._get_dossier_order(), "an SSS project is not an admin (Dossier) project")

        tasks = project.task_ids.sorted('name')
        self.assertEqual(tasks.mapped('name'), ['1.5 x Onduleur', '12 x Panneau 400W'])
        self.assertEqual(tasks.stage_id.name, 'SSS: À faire')
        self.assertFalse(tasks.user_ids, "SSS tasks are assigned later, during planning")
        self.assertEqual(tasks.mapped('allocated_hours'), [1.5, 12.0])
        self.assertEqual(order.x_sale_order_id_project_task_count, 2)
        action = self.env.ref('bgg_custom_dev.action_sale_order_tasks')
        domain = eval(action.domain, {'active_id': order.id})  # noqa: S307 - our own action domain
        self.assertEqual(self.env['project.task'].search(domain), project.task_ids)

        # run again: nothing duplicated
        result = order.action_create_sss_tasks()
        self.assertIn('Aucun élément créé', result['params']['message'])
        self.assertEqual(self.env['project.project'].search_count([('x_sss_sale_order_id', '=', order.id)]), 1)
        self.assertEqual(len(project.task_ids), 2)

    def test_existing_project_and_old_task_titles_are_reused(self):
        order = self._order()
        self._pay(order)
        # project created by the former Studio action: found by its name
        project = self.env['project.project'].create({
            'name': f"{order.name} - SSS - Client SSS", 'x_is_sss_project': True})
        self.env['project.task'].create({'name': 'Panneau 400W', 'project_id': project.id})
        order.action_create_sss_tasks()
        self.assertEqual(project.x_sss_sale_order_id, order)
        self.assertEqual(sorted(project.task_ids.mapped('name')), ['1.5 x Onduleur', 'Panneau 400W'])

    def test_no_manager_parameter(self):
        self.env['ir.config_parameter'].sudo().set_param('bgg.sss_project_manager_login', '')
        order = self._order()
        self._pay(order)
        order.action_create_sss_tasks()
        self.assertFalse(order._get_sss_project().user_id)


@tagged('post_install', '-at_install')
class TestStatusReminder(TransactionCase):
    """"Rappel pour statuer": a study RDV still booked one day after its end
    gets a To-Do for each commercial attendee."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        groups = cls.env['res.groups'].sudo()
        commercial_group = (groups.search([('name', '=ilike', 'Commercial')], limit=1)
                            or groups.create({'name': 'Commercial'}))
        base_group = cls.env.ref('base.group_user')
        cls.commercial = cls.env['res.users'].create({
            'name': 'Rappel Commercial', 'login': 'rappel_commercial', 'email': 'rappel@example.com',
            'group_ids': [(6, 0, [base_group.id, commercial_group.id])],
        })
        cls.other_user = cls.env['res.users'].create({
            'name': 'Rappel Autre', 'login': 'rappel_autre', 'email': 'rappel_autre@example.com',
            'group_ids': [(6, 0, [base_group.id])],
        })
        cls.customer = cls.env['res.partner'].create({'name': 'Client Rappel'})
        RdvType = cls.env['bgg.rdv.type']
        cls.study_type = RdvType.search([('code', '=', 'APT-ENERG-COM')]) or RdvType.create(
            {'name': 'Etude énergétique (par commercial)', 'code': 'APT-ENERG-COM'})
        cls.personal_type = RdvType.create({'name': 'RDV personnel (test)'})
        cls.postpone_tag = (cls.env['calendar.event.type'].search([('name', '=', 'à reporter')], limit=1)
                            or cls.env['calendar.event.type'].create({'name': 'à reporter'}))
        cls.todo = cls.env.ref('mail.mail_activity_data_todo')

    def _event(self, days_ago=2, status='booked', rdv_type=None, tags=None):
        stop = fields.Datetime.now() - datetime.timedelta(days=days_ago)
        event = self.env['calendar.event'].create({
            'name': 'RDV à statuer',
            'start': stop - datetime.timedelta(hours=1),
            'stop': stop,
            'partner_ids': [(6, 0, [self.customer.id, self.commercial.partner_id.id,
                                    self.other_user.partner_id.id])],
            'x_rdv_type_id': (rdv_type or self.study_type).id,
            'categ_ids': [(6, 0, (tags or self.env['calendar.event.type']).ids)],
        })
        event.with_context(skip_calendar_automation=True).write({'x_rdv_status': status})
        return event

    def _todos(self, event):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'calendar.event'), ('res_id', '=', event.id),
            ('activity_type_id', '=', self.todo.id)])

    def test_reminder_for_commercial_only(self):
        event = self._event()
        result = event.action_send_status_reminders()
        self.assertEqual(result['params']['type'], 'success')
        todos = self._todos(event)
        self.assertEqual(todos.user_id, self.commercial)
        self.assertEqual(todos.summary, 'Mise à jour du statut requise')
        self.assertIn('nécessite une mise à jour du statut', event.message_ids[0].body)
        # no second activity
        event.action_send_status_reminders()
        self.assertEqual(len(self._todos(event)), 1)

    def test_events_left_out(self):
        events = (self._event(days_ago=0)                          # not 24 h yet
                  | self._event(status='attended')                 # status set
                  | self._event(rdv_type=self.personal_type)       # not a study
                  | self._event(tags=self.postpone_tag))           # "à reporter"
        result = events.action_send_status_reminders()
        self.assertEqual(result['params']['title'], 'Aucun événement')
        for event in events:
            self.assertFalse(self._todos(event))

    def test_cron(self):
        due = self._event()
        postponed = self._event(tags=self.postpone_tag)
        self.env['calendar.event']._cron_send_status_reminders()
        self.assertEqual(self._todos(due).user_id, self.commercial)
        self.assertFalse(self._todos(postponed))
        self.assertFalse(self.env.ref('bgg_custom_dev.ir_cron_send_status_reminders').active,
                         "inactive like the Studio job it replaces")


@tagged('post_install', '-at_install')
class TestCloseProjects(TransactionCase):
    """"Clôturer les projets Admin/SSS": projects whose tasks are all closed
    go to the "Terminé" stage with the "Terminé" status."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Stage = cls.env['project.project.stage']
        cls.closed_stage = Stage.search([('name', '=', 'Terminé')], limit=1) or Stage.create({'name': 'Terminé'})

    def _project(self, *task_states):
        project = self.env['project.project'].create({'name': 'Projet à clôturer'})
        for state in task_states:
            self.env['project.task'].create({'name': 'Tâche', 'project_id': project.id, 'state': state})
        return project

    def test_close(self):
        done = self._project('1_done', '1_canceled')
        open_ = self._project('1_done', '01_in_progress')
        empty = self._project()
        result = (done | open_ | empty).action_close_projects()
        self.assertEqual(done.stage_id, self.closed_stage)
        self.assertEqual(done.last_update_status, 'done')
        self.assertNotEqual(open_.stage_id, self.closed_stage)
        self.assertNotEqual(empty.stage_id, self.closed_stage)
        self.assertEqual(result['params']['title'], 'Projets partiellement clôturés')
        self.assertIn('1 ignoré(s), tâches encore ouvertes', result['params']['message'])
        self.assertIn('1 ignoré(s), sans tâche', result['params']['message'])

        result = done.action_close_projects()
        self.assertEqual(result['params']['title'], 'Rien à faire')
