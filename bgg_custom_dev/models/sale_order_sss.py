# -*- coding: utf-8 -*-

import logging

from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)

# Email (or login) of the internal user set as project manager of every SSS
# project. Empty, or no matching active internal user: no project manager.
SSS_PROJECT_MANAGER_PARAM = 'bgg.sss_project_manager_login'
# Order lines that get an SSS task: consumable products of this product
# category (full name, its children included).
SSS_PRODUCT_CATEGORY = 'All / Saleable'
# A confirmed order gets its SSS project once one of its customer invoices is
# (partly) paid.
SSS_PAID_STATES = ('paid', 'partial', 'in_payment')
SSS_TASK_LABEL = 'Tâches - Service sur Site'
# Stages created on a new SSS project (French name, older English name
# created by the Studio action for English users). New tasks go to the first.
SSS_STAGES = [
    ('SSS: À faire', 'FSM: ToDo'),
    ('SSS: Encours/Fait', 'FSM: In progress/Done'),
]


class SaleOrder(models.Model):
    """Former Odoo Studio customizations of the sale order: fields (same
    names and link table, so their data stays in place) and the
    "Créer tâches SSS" action, which now creates a plain project flagged
    SSS (x_is_sss_project) instead of an Enterprise Field Service project.
    """
    _inherit = 'sale.order'

    x_studio_organisateur_du_rendez_vous = fields.Many2one(
        'res.users',
        string='Organisateur du rendez-vous',
        related='opportunity_id.calendar_event_ids.create_uid',
        store=True,
        readonly=True,
    )
    x_studio_rendez_vous_pris_la_place_de = fields.Many2one(
        'res.partner',
        string='Rendez-vous pris à la place de',
        related='opportunity_id.calendar_event_ids.x_studio_rendez_vous_pris_la_place_de',
        readonly=True,
    )
    x_studio_restant_a_facturer = fields.Float(
        string='Restant à facturer',
        readonly=True,
    )
    x_studio_vendeur_associes = fields.Many2many(
        'res.users',
        'x_res_users_sale_order_rel',
        'sale_order_id',
        'res_users_id',
        string='Vendeur associés',
    )
    # "Tâches" smart button: tasks linked to the order, and the tasks of its
    # SSS project (on Community a task without order line loses its order).
    x_sale_order_id_project_task_count = fields.Integer(
        string='Tâches',
        compute='_compute_sss_task_count',
    )

    @api.model
    def _sss_task_domain(self, order_id):
        return ['|', ('sale_order_id', '=', order_id),
                ('project_id.x_sss_sale_order_id', '=', order_id)]

    def _compute_sss_task_count(self):
        Task = self.env['project.task'].sudo()
        for order in self:
            order_id = order._origin.id
            order.x_sale_order_id_project_task_count = (
                Task.search_count(self._sss_task_domain(order_id)) if order_id else 0)

    # ------------------------------------------------------------------
    # "Créer tâches SSS": SSS project + one task per product to install
    # ------------------------------------------------------------------

    @api.model
    def _sss_project_manager(self):
        value = (self.env['ir.config_parameter'].sudo().get_param(SSS_PROJECT_MANAGER_PARAM) or '').strip()
        Users = self.env['res.users'].sudo()
        if not value:
            _logger.warning("SSS project manager: parameter %s is empty, projects will have no manager",
                            SSS_PROJECT_MANAGER_PARAM)
            return Users
        manager = Users.search([
            '|', ('email', '=ilike', value), ('login', '=ilike', value),
            ('share', '=', False),
        ], limit=1)
        if not manager:
            _logger.warning("SSS project manager: no active internal user with email or login '%s' "
                            "(parameter %s), projects will have no manager", value, SSS_PROJECT_MANAGER_PARAM)
        return manager

    def _sss_paid_invoices(self):
        self.ensure_one()
        invoices = self.invoice_ids | self.env['account.move'].search([
            ('invoice_origin', '=', self.name),
            ('move_type', '=', 'out_invoice'),
        ])
        return invoices.filtered(lambda m: m.move_type == 'out_invoice' and m.state == 'posted'
                                 and m.payment_state in SSS_PAID_STATES)

    def _sss_project_name(self):
        self.ensure_one()
        return f"{self.name} - SSS - {self.partner_id.name}"

    def _get_sss_project(self):
        self.ensure_one()
        return self.env['project.project'].search([
            ('x_is_sss_project', '=', True),
            '|', ('x_sss_sale_order_id', '=', self.id), ('name', '=', self._sss_project_name()),
        ], limit=1)

    @api.model
    def _sss_known_vals(self, model, vals):
        """vals without the fields of apps that are not installed (e.g.
        allow_timesheets needs Timesheets)."""
        fields_ = self.env[model]._fields
        return {key: value for key, value in vals.items() if key in fields_}

    def _bgg_sss_project_extra_vals(self):
        """Extra values of a new SSS project (Enterprise bridge: Field Service)."""
        return {}

    def _bgg_sss_task_extra_vals(self, line):
        """Extra values of a new SSS task (Enterprise bridge: Field Service)."""
        return {}

    def _sss_create_project(self, manager):
        self.ensure_one()
        vals = {
            'name': self._sss_project_name(),
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'user_id': manager.id or False,
            'x_is_sss_project': True,
            'x_sss_sale_order_id': self.id,
            'privacy_visibility': 'employees',
            'allow_task_dependencies': True,
            'allow_milestones': False,
            'allow_billable': False,
            'allow_timesheets': True,
            'label_tasks': SSS_TASK_LABEL,
        }
        vals.update(self._bgg_sss_project_extra_vals())
        project = self.env['project.project'].create(self._sss_known_vals('project.project', vals))
        self.env['project.task.type'].create([{
            'name': name,
            'sequence': sequence,
            'fold': False,
            'project_ids': [Command.link(project.id)],
        } for sequence, (name, _old_name) in enumerate(SSS_STAGES, start=1)])
        _logger.info("SSS project created: %s (ID %s), manager: %s",
                     project.name, project.id, project.user_id.name or 'none')
        return project

    def _sss_initial_stage(self, project):
        Stage = self.env['project.task.type']
        return (Stage.search([('name', 'in', list(SSS_STAGES[0])), ('project_ids', 'in', project.ids)], limit=1)
                or Stage.search([('project_ids', 'in', project.ids)], limit=1))

    def _sss_order_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda line: line.product_id and line.product_id.type == 'consu'
            and (line.product_id.categ_id.complete_name or '').startswith(SSS_PRODUCT_CATEGORY))

    @api.model
    def _sss_task_name(self, line):
        """"<quantity> x <product>", quantity without decimals when whole."""
        qty = line.product_uom_qty
        qty_text = str(int(qty)) if qty == int(qty) else f"{qty:g}"
        return f"{qty_text} x {line.product_id.name}"

    def _sss_create_tasks(self, project):
        self.ensure_one()
        Task = self.env['project.task']
        stage = self._sss_initial_stage(project)
        tasks = Task.browse()
        for line in self._sss_order_lines():
            name = self._sss_task_name(line)
            # also the older title without quantity (first Studio version)
            if Task.search_count([('project_id', '=', project.id),
                                  ('name', 'in', [name, line.product_id.name])], limit=1):
                continue
            hours = line.product_uom_qty if line.product_uom_qty > 0 else 1
            vals = {
                'name': name,
                'project_id': project.id,
                'partner_id': self.partner_id.id,
                'sale_order_id': self.id,
                'company_id': self.company_id.id,
                # unassigned: assigned later, during planning
                'user_ids': [Command.clear()],
                'allocated_hours': hours,
                'stage_id': stage.id,
                'state': '01_in_progress',
            }
            vals.update(self._bgg_sss_task_extra_vals(line))
            tasks |= Task.create(self._sss_known_vals('project.task', vals))
        return tasks

    def action_create_sss_tasks(self):
        """Create the SSS project of each confirmed and (partly) paid order,
        with one task per product to install. Projects and tasks that already
        exist are kept, so the action can be run again after a change."""
        manager = self._sss_project_manager()
        not_confirmed = not_paid = projects_created = tasks_created = 0
        for order in self:
            if order.state != 'sale':
                _logger.info("SSS: order %s is not confirmed (%s), skipped", order.name, order.state)
                not_confirmed += 1
                continue
            if not order._sss_paid_invoices():
                _logger.info("SSS: order %s has no paid invoice, skipped", order.name)
                not_paid += 1
                continue
            project = order._get_sss_project()
            if not project:
                project = order._sss_create_project(manager)
                projects_created += 1
            elif not project.x_sss_sale_order_id:
                project.x_sss_sale_order_id = order
            tasks = order._sss_create_tasks(project)
            tasks_created += len(tasks)
            _logger.info("SSS: order %s, project %s, %s task(s) created", order.name, project.name, len(tasks))

        invalid = not_confirmed + not_paid
        valid = len(self) - invalid
        if not valid:
            title, notif_type, sticky = 'Aucune commande valide', 'warning', True
            message = 'Aucune commande client payée (complètement/partiellement) sélectionnée.'
        else:
            title, notif_type, sticky = 'Tâches SSS', 'success', False
            parts = [f'{valid} commande(s) client valide(s) payée(s) (complètement/partiellement)'
                     + (f' / {invalid} non valide(s)' if invalid else '')]
            created = []
            if projects_created:
                created.append(f'{projects_created} projet(s) SSS créé(s)')
            if tasks_created:
                created.append(f'{tasks_created} tâche(s) SSS créée(s)')
            parts.append(' - '.join(created) or 'Aucun élément créé (projets/tâches déjà existants)')
            message = ' | '.join(parts)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notif_type,
                'sticky': sticky,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
