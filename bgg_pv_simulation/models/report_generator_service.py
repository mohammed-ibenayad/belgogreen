# -*- coding: utf-8 -*-
"""
Report Generator — HTTP client for external report service (Node.js + Puppeteer)
Replaces WeasyPrint-based generation with a call to the dedicated PDF microservice.
"""

import base64
import io
import logging
import requests

from odoo import models, api

_logger = logging.getLogger(__name__)

# Default service URL (override via system parameter 'pv_report_service_url')
DEFAULT_SERVICE_URL = 'http://localhost:3002'
TIMEOUT_SECONDS = 60


class PvSimulationReportService(models.AbstractModel):
    _name = 'pv.simulation.report.service'
    _description = 'Report Service Client for PV Simulation'

    @api.model
    def generate_report(self, simulation_id):
        """Generate a PDF report via the external report service."""
        simulation = self.env['pv.simulation'].browse(simulation_id)
        payload = self._prepare_report_payload(simulation)

        service_url = self.env['ir.config_parameter'].sudo().get_param(
            'pv_report_service_url', DEFAULT_SERVICE_URL
        )
        api_key = self.env['ir.config_parameter'].sudo().get_param(
            'pv_report_service_api_key', ''
        )

        url = f'{service_url}/api/reports/pv-simulation'
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            _logger.info("Report service returned PDF (%d bytes)", len(response.content))
            return response.content
        except requests.exceptions.ConnectionError:
            _logger.error("Cannot connect to report service at %s", url)
            raise Exception(
                "Cannot connect to the report generation service.\n"
                f"URL: {url}\n\n"
                "Make sure the belgogreen-report-service Docker container is running:\n"
                "  cd /opt/belgogreen-report-service && docker compose up -d"
            )
        except requests.exceptions.Timeout:
            _logger.error("Report service timed out after %ds", TIMEOUT_SECONDS)
            raise Exception("Report generation timed out. Please try again.")
        except requests.exceptions.HTTPError as e:
            _logger.error("Report service returned error: %s", e.response.text)
            raise Exception(f"Report service error: {e.response.status_code} — {e.response.text}")

    def _prepare_report_payload(self, simulation):
        """Serialize simulation data to JSON for the report service."""
        partner = simulation.sale_order_id.partner_id if simulation.sale_order_id else None
        company = simulation.company_id
        user = simulation.sale_order_id.user_id if simulation.sale_order_id else None

        # Ensure chart exists
        chart_data = simulation.chart_monthly_production
        if not chart_data and simulation.monthly_result_ids:
            try:
                generator = self.env['pv.simulation.weasyprint.generator']
                chart_buffer = generator._generate_monthly_chart(simulation)
                if chart_buffer:
                    chart_data = base64.b64encode(chart_buffer.getvalue())
            except Exception as e:
                _logger.warning("Could not generate chart: %s", e)

        # Bilan aggregations
        results = simulation.monthly_result_ids
        prod_total = simulation.annual_production_kwh or 0.0
        conso_day = sum(results.mapped('monthly_day_consumption_kwh')) if results else 0.0
        conso_night = sum(results.mapped('monthly_night_consumption_kwh')) if results else 0.0
        conso_total = sum(results.mapped('monthly_consumption_kwh')) if results else 0.0
        if not conso_total and hasattr(simulation, 'consumption_profile_id') and simulation.consumption_profile_id:
            conso_total = simulation.consumption_profile_id.annual_consumption_kwh or 0.0
        autocons_total = sum(results.mapped('monthly_autoconsumption_kwh')) if results else 0.0
        battery_charge = sum(results.mapped('monthly_battery_charge_kwh')) if results else 0.0
        autocons_direct = autocons_total - battery_charge
        savings_panels = sum(results.mapped('panel_savings')) if results else 0.0
        savings_battery = sum(results.mapped('battery_savings')) if results else 0.0
        savings_resale = sum(results.mapped('sale_revenue')) if results else 0.0
        savings_total = savings_panels + savings_battery + savings_resale
        purchase_total = sum(results.mapped('purchase_cost')) if results else 0.0

        return {
            'name': simulation.name or '',
            'report_date': simulation.report_date.strftime('%d/%m/%Y') if simulation.report_date else '',
            'installation_address': simulation.installation_address or '',
            'partner_name': partner.name if partner else '',

            # Cover
            'cover_title': simulation.cover_title or 'Votre installation',
            'cover_subtitle': simulation.cover_subtitle or 'Photovoltaïque',
            'tagline': company.pv_report_tagline or '',

            # Images (base64 data URIs)
            'cover_photo': self._to_data_uri(simulation.cover_photo),
            'location_image': self._to_data_uri(simulation.location_image),
            'system_image': self._to_data_uri(simulation.system_image),
            'chart_monthly_production': self._to_data_uri(chart_data),
            'logo': self._to_data_uri(company.pv_report_logo or company.logo),

            # System parameters
            'total_pv_power_wc': simulation.total_pv_power_wc or 0,
            'number_of_panels': simulation.number_of_panels or 0,
            'orientation_deg': simulation.orientation_deg or 0,
            'tilt_deg': simulation.tilt_deg or 0,
            'roof_surface_m2': simulation.roof_surface_m2 or 0,
            'annual_production_kwh': simulation.annual_production_kwh or 0,

            # Production source
            'production_source': (
                'PVGIS (EU Science Hub)' if simulation.pvgis_annual_production_kwh
                else 'Google Solar API'
            ),

            # Section titles
            'section_titles': {
                'location': simulation.section_title_location or "LOCALISATION DE L'INSTALLATION",
                'system': simulation.section_title_system or 'CARACTÉRISTIQUES DU SYSTÈME',
                'production': simulation.section_title_production or 'PRODUCTION ESTIMÉE',
                'bilan': simulation.section_title_bilan or 'BILAN ÉNERGÉTIQUE',
            },

            # Company
            'company': {
                'name': company.name or '',
                'phone': company.pv_report_phone or company.phone or '',
                'email': company.pv_report_email or company.email or '',
            },

            # Salesperson
            'salesperson': {
                'name': user.name if user else '',
                'phone': (user.phone if user else '') or company.pv_report_phone or company.phone or '',
                'email': (user.email if user else '') or company.pv_report_email or company.email or '',
            },

            # Bilan data
            'bilan': {
                'production_total': prod_total,
                'consumption_day': conso_day,
                'consumption_night': conso_night,
                'consumption_total': conso_total,
                'autoconsumption_direct': autocons_direct,
                'autoconsumption_total': autocons_total,
                'battery_charge': battery_charge,
                'savings_panels': savings_panels,
                'savings_battery': savings_battery,
                'savings_resale': savings_resale,
                'savings_total': savings_total,
                'purchase_total': purchase_total,
            },
        }

    @staticmethod
    def _to_data_uri(b64_field):
        """Convert an Odoo binary field to a data URI string."""
        if not b64_field:
            return ''
        if isinstance(b64_field, str):
            raw = base64.b64decode(b64_field)
            b64_str = b64_field
        else:
            raw = base64.b64decode(b64_field)
            b64_str = b64_field.decode()

        if raw[:2] == b'\xff\xd8':
            mime = 'image/jpeg'
        elif raw[:8] == b'\x89PNG\r\n\x1a\n':
            mime = 'image/png'
        elif raw[:6] in (b'GIF87a', b'GIF89a'):
            mime = 'image/gif'
        else:
            mime = 'image/png'

        return f'data:{mime};base64,{b64_str}'
