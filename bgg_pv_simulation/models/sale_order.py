# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    pv_simulation_id = fields.Many2one(
        'pv.simulation',
        string='PV Simulation',
        ondelete='restrict',
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
            # Open form to create new simulation with pre-filled values
            return {
                'type': 'ir.actions.act_window',
                'name': _('New PV Simulation'),
                'res_model': 'pv.simulation',
                'view_mode': 'form',
                'target': 'current',
                'context': {
                    'default_sale_order_id': self.id,
                    'default_currency_id': self.currency_id.id or self.env.company.currency_id.id,
                    'default_company_id': self.company_id.id or self.env.company.id,
                    'default_installation_address': self.partner_id.contact_address or self.partner_id.street or '',
                }
            }
