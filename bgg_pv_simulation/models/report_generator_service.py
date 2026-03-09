# -*- coding: utf-8 -*-
"""
Report Generator Service — HTTP client for the external PDF report service.

Calls the BelGoGreen Report Service (Puppeteer/Chromium on VPS) to generate
premium PDF reports. The service URL and API key are read from Odoo system
parameters (ir.config_parameter):

  report_service_url     = http://72.61.95.153
  report_service_api_key = <secret>
"""

import base64
import logging

import requests
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 120


class PvSimulationServiceGenerator(models.AbstractModel):
    _name = 'pv.simulation.service.generator'
    _description = 'External Report Service Generator for PV Simulation'

    @api.model
    def generate_report(self, simulation_id):
        """Generate a PDF report via the external report service."""
        simulation = self.env['pv.simulation'].browse(simulation_id)
        if not simulation.exists():
            raise UserError(_('Simulation record not found.'))

        # Read service config from system parameters
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = (ICP.get_param('report_service_url') or '').rstrip('/')
        api_key = ICP.get_param('report_service_api_key') or ''

        if not base_url:
            raise UserError(_(
                'Report service URL is not configured.\n\n'
                'Go to Settings → Technical → Parameters → System Parameters and set:\n'
                '  report_service_url = http://72.61.95.153'
            ))
        if not api_key:
            raise UserError(_(
                'Report service API key is not configured.\n\n'
                'Go to Settings → Technical → Parameters → System Parameters and set:\n'
                '  report_service_api_key = <your-secret-key>'
            ))

        url = f'{base_url}/api/reports/pv-simulation'
        payload = self._build_payload(simulation)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }

        _logger.info('Calling report service: POST %s (simulation=%s)', url, simulation.name)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
        except requests.exceptions.ConnectionError:
            raise UserError(_(
                'Cannot connect to the report generation service.\n'
                'URL: %s\n\n'
                'Make sure:\n'
                '1. The belgogreen-report-service Docker container is running on the VPS\n'
                '2. Nginx is configured to proxy requests to port 3002\n'
                '3. The VPS firewall allows port 80'
            ) % url)
        except requests.exceptions.Timeout:
            raise UserError(_(
                'Report generation timed out after %d seconds.\n'
                'The PDF may be too complex. Try again or contact support.'
            ) % TIMEOUT_SECONDS)

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else 'No details'
            _logger.error('Report service returned %s: %s', response.status_code, error_detail)
            raise UserError(_(
                'Report service returned an error (HTTP %s).\n\n%s'
            ) % (response.status_code, error_detail))

        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' not in content_type:
            _logger.error('Unexpected content type: %s', content_type)
            raise UserError(_('Report service did not return a PDF. Content-Type: %s') % content_type)

        _logger.info('PDF received (%d bytes) for simulation %s', len(response.content), simulation.name)
        return response.content

    def _build_payload(self, simulation):
        """Build the JSON payload expected by the report service."""
        partner = simulation.sale_order_id.partner_id if simulation.sale_order_id else None
        company = simulation.company_id
        user = simulation.sale_order_id.user_id if simulation.sale_order_id else None

        def _b64_to_data_uri(b64_field):
            """Convert an Odoo binary field to a data URI string."""
            if not b64_field:
                return None
            raw = base64.b64decode(b64_field)
            if raw[:2] == b'\xff\xd8':
                mime = 'image/jpeg'
            elif raw[:8] == b'\x89PNG\r\n\x1a\n':
                mime = 'image/png'
            else:
                mime = 'image/png'
            return f'data:{mime};base64,{b64_field.decode() if isinstance(b64_field, bytes) else b64_field}'

        # Monthly results
        monthly_results = []
        for r in simulation.monthly_result_ids.sorted(lambda r: int(r.month)):
            monthly_results.append({
                'month': int(r.month),
                'daily_production_kwh': r.daily_production_kwh,
                'production_pv_kwh': r.production_pv_kwh if hasattr(r, 'production_pv_kwh') else 0,
                'monthly_consumption_kwh': r.monthly_consumption_kwh if hasattr(r, 'monthly_consumption_kwh') else 0,
                'monthly_day_consumption_kwh': r.monthly_day_consumption_kwh if hasattr(r, 'monthly_day_consumption_kwh') else 0,
                'monthly_night_consumption_kwh': r.monthly_night_consumption_kwh if hasattr(r, 'monthly_night_consumption_kwh') else 0,
                'monthly_autoconsumption_kwh': r.monthly_autoconsumption_kwh if hasattr(r, 'monthly_autoconsumption_kwh') else 0,
                'monthly_battery_charge_kwh': r.monthly_battery_charge_kwh if hasattr(r, 'monthly_battery_charge_kwh') else 0,
                'panel_savings': r.panel_savings if hasattr(r, 'panel_savings') else 0,
                'battery_savings': r.battery_savings if hasattr(r, 'battery_savings') else 0,
                'sale_revenue': r.sale_revenue if hasattr(r, 'sale_revenue') else 0,
                'purchase_cost': r.purchase_cost if hasattr(r, 'purchase_cost') else 0,
            })

        # Address
        address_parts = []
        if partner:
            if partner.street:
                address_parts.append(partner.street)
            if partner.street2:
                address_parts.append(partner.street2)
            city_line = ' '.join(filter(None, [partner.zip, partner.city]))
            if city_line:
                address_parts.append(city_line)
            if partner.country_id and partner.country_id.name:
                address_parts.append(partner.country_id.name)

        logo_uri = _b64_to_data_uri(company.pv_report_logo or company.logo)
        tagline = company.pv_report_tagline or ''
        partner_name = partner.name if partner else ''
        installation_address = '\n'.join(address_parts)

        payload = {
            'name': simulation.name or '',
            'report_date': simulation.report_date.strftime('%d/%m/%Y') if simulation.report_date else '',

            # Company
            'company': {
                'name': company.name or '',
                'phone': company.pv_report_phone or company.phone or '',
                'email': company.pv_report_email or company.email or '',
                'logo': logo_uri,
                'tagline': tagline,
            },

            # Salesperson
            'salesperson': {
                'name': user.name if user else '',
                'phone': (user.phone if user else '') or company.phone or '',
                'email': (user.email if user else '') or company.email or '',
            },

            # Customer
            'customer': {
                'name': partner_name,
                'address': installation_address,
            },

            # Top-level fields expected by report templates
            'logo': logo_uri,
            'tagline': tagline,
            'partner_name': partner_name,
            'installation_address': installation_address,

            # Images (as data URIs)
            'cover_photo': _b64_to_data_uri(simulation.cover_photo),
            'location_image': _b64_to_data_uri(simulation.location_image),
            'system_image': _b64_to_data_uri(simulation.system_image),
            'chart_monthly_production': _b64_to_data_uri(simulation.chart_monthly_production),

            # Cover text
            'cover_title': simulation.cover_title or 'Votre installation',
            'cover_subtitle': simulation.cover_subtitle or 'Photovoltaïque',

            # Section titles
            'section_titles': {
                'location': simulation.section_title_location or "LOCALISATION DE L'INSTALLATION",
                'system': simulation.section_title_system or 'CARACTÉRISTIQUES DU SYSTÈME',
                'production': simulation.section_title_production or 'PRODUCTION ESTIMÉE',
                'bilan': simulation.section_title_bilan or 'BILAN ÉNERGÉTIQUE',
            },

            # PV system
            'total_pv_power_wc': simulation.total_pv_power_wc or 0,
            'number_of_panels': simulation.number_of_panels or 0,
            'orientation_deg': simulation.orientation_deg or 0,
            'tilt_deg': simulation.tilt_deg or 0,
            'roof_surface_m2': simulation.roof_surface_m2 or 0,
            'annual_production_kwh': simulation.annual_production_kwh or 0,

            # Bilan
            'bilan': self._build_bilan(simulation),

            # Monthly data
            'monthly_results': monthly_results,
        }

        return payload

    def _build_bilan(self, simulation):
        """Build the energy balance summary."""
        results = simulation.monthly_result_ids
        if not results:
            return {}

        prod_total = simulation.annual_production_kwh or 0.0
        conso_day = sum(results.mapped('monthly_day_consumption_kwh')) if hasattr(results[0], 'monthly_day_consumption_kwh') else 0
        conso_night = sum(results.mapped('monthly_night_consumption_kwh')) if hasattr(results[0], 'monthly_night_consumption_kwh') else 0
        conso_total = sum(results.mapped('monthly_consumption_kwh')) if hasattr(results[0], 'monthly_consumption_kwh') else 0
        autocons_total = sum(results.mapped('monthly_autoconsumption_kwh')) if hasattr(results[0], 'monthly_autoconsumption_kwh') else 0
        battery_charge = sum(results.mapped('monthly_battery_charge_kwh')) if hasattr(results[0], 'monthly_battery_charge_kwh') else 0
        savings_panels = sum(results.mapped('panel_savings')) if hasattr(results[0], 'panel_savings') else 0
        savings_battery = sum(results.mapped('battery_savings')) if hasattr(results[0], 'battery_savings') else 0
        savings_resale = sum(results.mapped('sale_revenue')) if hasattr(results[0], 'sale_revenue') else 0
        purchase_total = sum(results.mapped('purchase_cost')) if hasattr(results[0], 'purchase_cost') else 0

        return {
            'production_total': prod_total,
            'consumption_day': conso_day,
            'consumption_night': conso_night,
            'consumption_total': conso_total,
            'autoconsumption_direct': autocons_total - battery_charge,
            'autoconsumption_battery': battery_charge,
            'autoconsumption_total': autocons_total,
            'savings_panels': savings_panels,
            'savings_battery': savings_battery,
            'savings_resale': savings_resale,
            'savings_total': savings_panels + savings_battery + savings_resale,
            'purchase_total': purchase_total,
        }
