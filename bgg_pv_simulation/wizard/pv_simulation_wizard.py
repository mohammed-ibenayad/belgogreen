# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PvSimulationWizard(models.TransientModel):
    _name = 'pv.simulation.wizard'
    _description = 'PV Simulation Creation Wizard'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Devis',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        related='sale_order_id.partner_id',
        string='Client',
    )
    installation_address = fields.Text(
        string="Adresse d'installation",
        compute='_compute_installation_address',
        readonly=True,
    )

    # GPS
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        required=True,
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        required=True,
    )

    # Consumption
    default_monthly_consumption_kwh = fields.Float(
        string='Consommation mensuelle',
        help='Consommation totale mensuelle en kWh',
    )
    default_daily_day_consumption_kwh = fields.Float(
        string='Consommation jour quotidienne',
        help='Consommation quotidienne en journée en kWh',
    )
    default_daily_night_consumption_kwh = fields.Float(
        string='Consommation nuit quotidienne',
        help='Consommation quotidienne la nuit en kWh',
    )

    @api.depends('sale_order_id')
    def _compute_installation_address(self):
        for wiz in self:
            partner = wiz.sale_order_id.partner_id
            if partner:
                parts = [
                    partner.street or '',
                    partner.street2 or '',
                    ' '.join(filter(None, [partner.zip or '', partner.city or ''])),
                    partner.country_id.name or '',
                ]
                wiz.installation_address = '\n'.join(p for p in parts if p)
            else:
                wiz.installation_address = ''

    def action_create_simulation(self):
        """Create the simulation with wizard data and open the form."""
        self.ensure_one()
        self._validate_inputs()

        simulation = self.env['pv.simulation'].create(
            self._prepare_simulation_vals()
        )
        # Apply default consumption to all monthly results
        simulation.action_apply_default_consumption()

        return {
            'type': 'ir.actions.act_window',
            'name': _('PV Simulation'),
            'res_model': 'pv.simulation',
            'res_id': simulation.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_and_generate(self):
        """Create the simulation and immediately regenerate it."""
        self.ensure_one()
        self._validate_inputs()

        simulation = self.env['pv.simulation'].create(
            self._prepare_simulation_vals()
        )
        simulation.action_do_regenerate()
        simulation.action_apply_default_consumption()
        simulation.action_compute_daily_balance()

        return {
            'type': 'ir.actions.act_window',
            'name': _('PV Simulation'),
            'res_model': 'pv.simulation',
            'res_id': simulation.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _validate_inputs(self):
        if not self.latitude or not self.longitude:
            raise UserError(_('Veuillez saisir les coordonnées GPS (latitude et longitude).'))

    def _prepare_simulation_vals(self):
        return {
            'sale_order_id': self.sale_order_id.id,
            'currency_id': self.sale_order_id.currency_id.id or self.env.company.currency_id.id,
            'company_id': self.sale_order_id.company_id.id or self.env.company.id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'default_monthly_consumption_kwh': self.default_monthly_consumption_kwh,
            'default_daily_day_consumption_kwh': self.default_daily_day_consumption_kwh,
            'default_daily_night_consumption_kwh': self.default_daily_night_consumption_kwh,
        }
