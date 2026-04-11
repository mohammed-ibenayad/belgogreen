# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    pv_simulation_id = fields.Many2one(
        'pv.simulation',
        string='Simulation PV',
        ondelete='set null',
        copy=False
    )
    pv_simulation_ids = fields.One2many(
        'pv.simulation',
        'sale_order_id',
        string='Simulations PV',
    )
    pv_simulation_count = fields.Integer(
        compute='_compute_pv_simulation_count',
        string='Nombre de simulations'
    )

    @api.depends('pv_simulation_ids')
    def _compute_pv_simulation_count(self):
        for order in self:
            order.pv_simulation_count = len(order.pv_simulation_ids)

    def action_open_pv_simulation(self):
        """Open PV simulation list or wizard depending on count."""
        self.ensure_one()

        if self.pv_simulation_count == 0:
            # No simulations: open wizard to create one
            return {
                'type': 'ir.actions.act_window',
                'name': _('Nouvelle Simulation PV'),
                'res_model': 'pv.simulation.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_sale_order_id': self.id,
                },
            }
        else:
            # 1+ simulations: show list with ability to create new
            return {
                'type': 'ir.actions.act_window',
                'name': _('Simulations PV'),
                'res_model': 'pv.simulation',
                'view_mode': 'list,form',
                'domain': [('sale_order_id', '=', self.id)],
                'context': {
                    'default_sale_order_id': self.id,
                    'create': False,
                },
            }
