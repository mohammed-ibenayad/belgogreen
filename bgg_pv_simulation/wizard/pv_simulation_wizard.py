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

    # GPS — Char fields to avoid locale issues when pasting coordinates
    # (e.g. French locale interprets "50.727" dot as thousands separator)
    latitude = fields.Char(
        string='Latitude',
        required=True,
    )
    longitude = fields.Char(
        string='Longitude',
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

    def _parse_coordinate(self, value, field_label):
        """Parse a coordinate string to float, accepting both dot and comma as decimal separator."""
        if not value or not value.strip():
            raise UserError(_('Veuillez saisir la %s.') % field_label)
        # Normalize: replace comma with dot, strip spaces
        cleaned = value.strip().replace(',', '.')
        # Remove any thousands separators (dots that are not the last dot)
        parts = cleaned.split('.')
        if len(parts) > 2:
            # Multiple dots: keep last one as decimal separator, remove the rest
            cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
        try:
            return float(cleaned)
        except ValueError:
            raise UserError(_('Valeur invalide pour %s: "%s". Utilisez un format comme 50.8503396') % (field_label, value))

    def _get_parsed_coordinates(self):
        """Parse and validate latitude/longitude, return (lat, lng) as floats."""
        lat = self._parse_coordinate(self.latitude, _('latitude'))
        lng = self._parse_coordinate(self.longitude, _('longitude'))
        if not (-90 <= lat <= 90):
            raise UserError(_('La latitude doit être comprise entre -90 et 90. Valeur actuelle: %s') % lat)
        if not (-180 <= lng <= 180):
            raise UserError(_('La longitude doit être comprise entre -180 et 180. Valeur actuelle: %s') % lng)
        return lat, lng

    def action_create_simulation(self):
        """Create the simulation with wizard data and open the form."""
        self.ensure_one()
        lat, lng = self._get_parsed_coordinates()

        simulation = self.env['pv.simulation'].create(
            self._prepare_simulation_vals(lat, lng)
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
        """Create the simulation and launch generation with loading screen."""
        self.ensure_one()
        lat, lng = self._get_parsed_coordinates()

        simulation = self.env['pv.simulation'].create(
            self._prepare_simulation_vals(lat, lng)
        )

        # Return client action that shows loading screen during generation
        return {
            'type': 'ir.actions.client',
            'tag': 'pv_simulation_generate',
            'name': 'Génération',
            'target': 'current',
            'context': {'simulation_id': simulation.id},
        }

    def _prepare_simulation_vals(self, latitude, longitude):
        return {
            'sale_order_id': self.sale_order_id.id,
            'currency_id': self.sale_order_id.currency_id.id or self.env.company.currency_id.id,
            'company_id': self.sale_order_id.company_id.id or self.env.company.id,
            'latitude': latitude,
            'longitude': longitude,
            'default_monthly_consumption_kwh': self.default_monthly_consumption_kwh,
            'default_daily_day_consumption_kwh': self.default_daily_day_consumption_kwh,
            'default_daily_night_consumption_kwh': self.default_daily_night_consumption_kwh,
        }
