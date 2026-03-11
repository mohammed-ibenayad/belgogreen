# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    pv_simulation_id = fields.Many2one(
        'pv.simulation',
        string='PV Simulation',
        ondelete='set null',
        copy=False
    )
    pv_simulation_count = fields.Integer(
        compute='_compute_pv_simulation_count',
        string='Simulation Count'
    )

    @api.depends('pv_simulation_id')
    def _compute_pv_simulation_count(self):
        for order in self:
            order.pv_simulation_count = 1 if order.pv_simulation_id else 0

    def action_open_pv_simulation(self):
        """Open PV simulation form"""
        self.ensure_one()

        if self.pv_simulation_id:
            # Open existing simulation
            return {
                'type': 'ir.actions.act_window',
                'name': _('PV Simulation'),
                'res_model': 'pv.simulation',
                'res_id': self.pv_simulation_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Open wizard to collect GPS & consumption data before creating
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
