# -*- coding: utf-8 -*-

import logging
import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.product_template import _is_panel_category, _is_battery_category

_logger = logging.getLogger(__name__)


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

    # GPS — determined from address via Google Geocoding API
    latitude = fields.Char(
        string='Latitude',
    )
    longitude = fields.Char(
        string='Longitude',
    )

    # Panel orientation & inclination
    tilt_deg = fields.Float(
        string='Inclinaison (°)',
        default=35.0,
        help='Inclinaison des panneaux en degrés (0-90)',
    )
    orientation_deg = fields.Float(
        string='Orientation (°)',
        required=True,
        help='Orientation des panneaux en degrés (-180 à 180, 0=Sud)',
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

    # Validation notes (computed)
    missing_data_warning = fields.Text(
        string='Données manquantes',
        compute='_compute_missing_data_warning',
    )
    can_generate = fields.Boolean(
        string='Peut générer',
        compute='_compute_missing_data_warning',
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

    @api.depends('sale_order_id')
    def _compute_missing_data_warning(self):
        for wiz in self:
            warnings = []
            has_panels = False
            if wiz.sale_order_id:
                panel_lines = wiz.sale_order_id.order_line.filtered(
                    lambda l: _is_panel_category(l.product_id)
                )
                battery_lines = wiz.sale_order_id.order_line.filtered(
                    lambda l: _is_battery_category(l.product_id)
                )
                has_panels = bool(panel_lines)

                if not panel_lines:
                    warnings.append(
                        _("⚠ Aucun produit panneau PV trouvé dans le devis. "
                          "Ajoutez un produit de la catégorie 'Panneaux' pour que la puissance PV soit détectée.")
                    )
                else:
                    has_power = any(l.product_id.panel_unit_power_wc for l in panel_lines)
                    if not has_power:
                        warnings.append(
                            _("⚠ La puissance unitaire (Wc) n'est pas configurée sur le produit panneau. "
                              "Configurez le champ 'Panel Unit Power (Wc)' sur la fiche produit.")
                        )
                if not battery_lines:
                    warnings.append(
                        _("ℹ Aucune batterie trouvée dans le devis. La simulation sera sans stockage.")
                    )
                else:
                    has_capacity = any(l.product_id.battery_capacity_kwh for l in battery_lines)
                    if not has_capacity:
                        warnings.append(
                            _("⚠ La capacité de la batterie (kWh) n'est pas configurée sur le produit batterie. "
                              "Configurez le champ 'Battery Capacity (kWh)' sur la fiche produit.")
                        )
            wiz.missing_data_warning = '\n'.join(warnings) if warnings else ''
            wiz.can_generate = has_panels

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        sale_order_id = res.get('sale_order_id') or self.env.context.get('default_sale_order_id')
        if sale_order_id:
            sale_order = self.env['sale.order'].browse(sale_order_id)
            partner = sale_order.partner_id
            if partner:
                lat, lng = self._geocode_address(partner)
                if lat and lng:
                    res['latitude'] = str(lat)
                    res['longitude'] = str(lng)
        return res

    def _geocode_address(self, partner):
        """Use Google Geocoding API to get coordinates from partner address."""
        api_key = self.env['ir.config_parameter'].sudo().get_param('google_api_key')
        if not api_key:
            _logger.warning("Google API key not configured (google_api_key)")
            return None, None

        address_parts = [
            partner.street or '',
            partner.street2 or '',
            partner.zip or '',
            partner.city or '',
            partner.country_id.name or '',
        ]
        address = ', '.join(p for p in address_parts if p)
        if not address:
            return None, None

        try:
            response = requests.get(
                'https://maps.googleapis.com/maps/api/geocode/json',
                params={
                    'address': address,
                    'key': api_key,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'OK' and data.get('results'):
                location = data['results'][0]['geometry']['location']
                return location['lat'], location['lng']
            else:
                _logger.warning("Geocoding failed for address '%s': %s", address, data.get('status'))
                return None, None
        except Exception as e:
            _logger.warning("Geocoding error for address '%s': %s", address, e)
            return None, None

    def _parse_coordinate(self, value, field_label):
        """Parse a coordinate string to float, accepting both dot and comma as decimal separator."""
        if not value or not value.strip():
            raise UserError(_('Veuillez saisir la %s.') % field_label)
        cleaned = value.strip().replace(',', '.')
        parts = cleaned.split('.')
        if len(parts) > 2:
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

    def action_create_and_generate(self):
        """Create the simulation and launch generation with loading screen."""
        self.ensure_one()
        if not self.can_generate:
            raise UserError(_(
                "Impossible de générer la simulation. "
                "Veuillez vérifier que le devis contient un produit panneau PV avec la puissance configurée."
            ))
        lat, lng = self._get_parsed_coordinates()

        simulation = self.env['pv.simulation'].create(
            self._prepare_simulation_vals(lat, lng)
        )

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
            'latitude': str(latitude),
            'longitude': str(longitude),
            'tilt_deg': self.tilt_deg,
            'orientation_deg': self.orientation_deg,
            'default_monthly_consumption_kwh': self.default_monthly_consumption_kwh,
            'default_daily_day_consumption_kwh': self.default_daily_day_consumption_kwh,
            'default_daily_night_consumption_kwh': self.default_daily_night_consumption_kwh,
        }
