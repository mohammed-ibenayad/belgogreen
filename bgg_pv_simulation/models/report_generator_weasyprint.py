# -*- coding: utf-8 -*-
"""
PHOTOVOLTAIC REPORT DESIGN SYSTEM v4.0
WeasyPrint-based PDF Report Generator — Premium Solar Proposal

COLOR PALETTE:
- Primary Green:     #4A9B5D  (accents, savings, title accent)
- Dark Green:        #388E3C  (hover/emphasis)
- Light Green BG:    #E8F5E9  (eco impact backgrounds)
- Deep Charcoal:     #212121  (primary text)
- Secondary Text:    #616161  (metadata, labels)
- Light Grey BG:     #F9F9F9  (zebra rows, card backgrounds)
- Border Grey:       #E0E0E0  (borders, dividers)
- White:             #FFFFFF  (page background, card fills)

LAYOUT:
- WeasyPrint-optimized: tables + inline-block (no CSS grid, no flex-gap)
- Page size: A4 (210mm x 297mm)
- Margins: 25mm top, 20mm sides, 22mm bottom (except cover: 0)
"""

import io
import base64
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

# SVG icons for metric cards (inline, WeasyPrint-safe)
SVG_ICON_SUN = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>'
SVG_ICON_PANELS = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="12" y1="3" x2="12" y2="17"/><line x1="2" y1="10" x2="22" y2="10"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>'
SVG_ICON_COMPASS = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" fill="#4A9B5D" opacity="0.3"/></svg>'
SVG_ICON_TILT = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 20L2 20"/><path d="M4 20L18 6"/><path d="M18 6L18 14"/><path d="M14 10L18 6" stroke-dasharray="2 2"/></svg>'
SVG_ICON_PIN = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="#4A9B5D" stroke="#FFFFFF" stroke-width="1.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3" fill="#FFFFFF"/></svg>'

# Bilan page SVG icons
SVG_ICON_BOLT = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>'
SVG_ICON_HOME = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>'
SVG_ICON_MOON = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>'
SVG_ICON_BATTERY = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="6" width="18" height="12" rx="2" ry="2"/><line x1="23" y1="13" x2="23" y2="11"/><line x1="7" y1="10" x2="7" y2="14"/><line x1="5" y1="12" x2="9" y2="12"/></svg>'
SVG_ICON_RECYCLE = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>'
SVG_ICON_EURO = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17.2 7A6 6 0 0 0 7 12a6 6 0 0 0 10.2 5"/><line x1="4" y1="10" x2="14" y2="10"/><line x1="4" y1="14" x2="14" y2="14"/></svg>'
SVG_ICON_PIGGY = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 5c-1.5 0-2.8 1.4-3 2-3.5-1.5-11-.3-11 5 0 1.8 0 3 2 4.5V20h4v-2h3v2h4v-4c1-.5 1.7-1 2-2h2v-4h-2c0-1-.5-1.5-1-2"/><path d="M2 9.5a1 1 0 0 1 1-1h.01"/><circle cx="12.5" cy="9.5" r=".5" fill="#FFFFFF"/></svg>'
SVG_ICON_WALLET = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/><circle cx="18" cy="15" r="1.5"/></svg>'


class PvSimulationWeasyPrint(models.AbstractModel):
    """WeasyPrint-based PDF Report Generator — Design System v4.0"""
    _name = 'pv.simulation.weasyprint.generator'
    _description = 'WeasyPrint Report Generator for PV Simulation'

    @api.model
    def generate_report(self, simulation_id):
        """Generate a PDF report using WeasyPrint (HTML/CSS)"""
        try:
            from weasyprint import HTML, CSS
        except ImportError as e:
            _logger.error(f"WeasyPrint not installed: {e}")
            raise Exception(
                "WeasyPrint is required for this report.\n\n"
                "Installation:\n"
                "  pip install weasyprint\n\n"
                "Note: WeasyPrint requires system libraries (Cairo, Pango, GDK-PixBuf).\n"
                "On Ubuntu/Debian: sudo apt-get install libcairo2 libpango-1.0-0 libpangocairo-1.0-0\n"
                "If you're on Odoo.sh or cloud environment, add 'weasyprint>=60.0' to requirements.txt"
            )

        simulation = self.env['pv.simulation'].browse(simulation_id)
        html_content = self._generate_html(simulation)
        css_content = self._generate_css()

        try:
            pdf_bytes = HTML(string=html_content).write_pdf(
                stylesheets=[CSS(string=css_content)]
            )
            _logger.info("WeasyPrint PDF generated successfully")
            return pdf_bytes
        except Exception as e:
            _logger.error(f"Failed to generate WeasyPrint PDF: {e}")
            raise

    def _generate_html(self, simulation):
        """Generate HTML content for the report"""

        partner = simulation.sale_order_id.partner_id if simulation.sale_order_id else None
        company = simulation.company_id
        user = simulation.sale_order_id.user_id if simulation.sale_order_id else None

        def _make_data_uri(b64_field):
            if not b64_field:
                return ""
            import base64 as _base64
            raw = _base64.b64decode(b64_field)
            if raw[:2] == b'\xff\xd8':
                mime = 'image/jpeg'
            elif raw[:8] == b'\x89PNG\r\n\x1a\n':
                mime = 'image/png'
            elif raw[:6] in (b'GIF87a', b'GIF89a'):
                mime = 'image/gif'
            else:
                mime = 'image/png'
            return f"data:{mime};base64,{b64_field.decode()}"

        def _esc(value):
            if not value:
                return ''
            from markupsafe import escape
            return str(escape(str(value)))

        # Encode images
        logo_data = _make_data_uri(company.logo)
        cover_photo_data = _make_data_uri(simulation.cover_photo)
        location_image_data = _make_data_uri(simulation.location_image)
        system_image_data = _make_data_uri(simulation.system_image)
        chart_data = _make_data_uri(simulation.chart_monthly_production)

        if not chart_data and simulation.monthly_result_ids:
            try:
                chart_buffer = self._generate_monthly_chart(simulation)
                if chart_buffer:
                    chart_data = f"data:image/png;base64,{base64.b64encode(chart_buffer.getvalue()).decode()}"
            except Exception as e:
                _logger.warning(f"Could not generate chart: {e}")

        # Text fields
        cover_title = _esc(simulation.cover_title or 'Votre installation')
        cover_subtitle = _esc(simulation.cover_subtitle or 'Photovoltaïque')
        tagline = ''
        title_location = _esc(simulation.section_title_location or "LOCALISATION DE L'INSTALLATION")
        title_system = _esc(simulation.section_title_system or 'CARACTÉRISTIQUES DU SYSTÈME')
        title_production = _esc(simulation.section_title_production or 'PRODUCTION ESTIMÉE')
        title_bilan = _esc(simulation.section_title_bilan or 'BILAN ÉNERGÉTIQUE')
        title_consumption = _esc(simulation.section_title_consumption or 'DONNÉES DE CONSOMMATION')
        title_monthly_data = _esc(simulation.section_title_monthly_data or 'DONNÉES MENSUELLES')
        title_daily_balance = _esc(simulation.section_title_daily_balance or 'BILAN ÉNERGÉTIQUE QUOTIDIEN')

        # Footer
        company_name = _esc(company.name or '')
        company_phone = _esc(company.phone or '')
        company_email = _esc(company.email or '')
        address = _esc(simulation.installation_address or '')
        sp_name = _esc(user.name) if user else ''
        sp_phone = _esc(user.phone or company.phone or '') if user else company_phone
        sp_email = _esc(user.email or getattr(user, 'login', '') or '') if user else company_email

        footer_parts = []
        if company_name:
            footer_parts.append(company_name)
        if sp_phone:
            footer_parts.append(f'&#9742; {sp_phone}')
        if sp_email:
            footer_parts.append(f'&#9993; {sp_email}')
        footer_line = ' &nbsp;|&nbsp; '.join(footer_parts)

        # Partner
        partner_name = _esc(partner.name) if partner else ''
        report_date = simulation.report_date.strftime('%d/%m/%Y') if simulation.report_date else ''
        project_ref = _esc(simulation.sale_order_id.name or simulation.name or '')

        # Bilan data
        results = simulation.monthly_result_ids
        prod_total = simulation.pvgis_annual_production_kwh or simulation.annual_production_kwh or 0.0
        conso_day = sum(results.mapped('monthly_day_consumption_kwh')) if results else 0.0
        conso_night = sum(results.mapped('monthly_night_consumption_kwh')) if results else 0.0
        conso_total = sum(results.mapped('monthly_consumption_kwh')) if results else 0.0
        autocons_total = sum(results.mapped('monthly_autoconsumption_kwh')) if results else 0.0
        battery_charge = sum(results.mapped('monthly_battery_charge_kwh')) if results else 0.0
        autocons_day = autocons_total - battery_charge
        savings_panels = sum(results.mapped('panel_savings')) if results else 0.0
        savings_battery = sum(results.mapped('battery_savings')) if results else 0.0
        savings_resale = sum(results.mapped('sale_revenue')) if results else 0.0
        savings_total = savings_panels + savings_battery + savings_resale
        purchase_total = sum(results.mapped('purchase_cost')) if results else 0.0

        def _fmt(val):
            if not val:
                return '—'
            return f'{val:,.2f}'

        # Build metric cards list
        metric_cards_list = []
        metric_cards_list.append(f'''
            <div class="card">
                <div class="card-icon">{SVG_ICON_SUN}</div>
                <div class="card-text">
                    <div class="card-value">{simulation.total_pv_power_wc:,.0f}</div>
                    <div class="card-unit">Wc</div>
                    <div class="card-label">Puissance install\u00e9e</div>
                </div>
            </div>''')

        if simulation.number_of_panels:
            metric_cards_list.append(f'''
            <div class="card">
                <div class="card-icon">{SVG_ICON_PANELS}</div>
                <div class="card-text">
                    <div class="card-value">{simulation.number_of_panels}</div>
                    <div class="card-unit">panneaux</div>
                    <div class="card-label">Nombre de panneaux</div>
                </div>
            </div>''')

        if simulation.orientation_deg:
            metric_cards_list.append(f'''
            <div class="card">
                <div class="card-icon">{SVG_ICON_COMPASS}</div>
                <div class="card-text">
                    <div class="card-value">{simulation.orientation_deg:.0f}\u00b0</div>
                    <div class="card-unit">&nbsp;</div>
                    <div class="card-label">Orientation</div>
                </div>
            </div>''')

        if simulation.tilt_deg:
            metric_cards_list.append(f'''
            <div class="card">
                <div class="card-icon">{SVG_ICON_TILT}</div>
                <div class="card-text">
                    <div class="card-value">{simulation.tilt_deg:.0f}\u00b0</div>
                    <div class="card-unit">&nbsp;</div>
                    <div class="card-label">Inclinaison</div>
                </div>
            </div>''')

        # Split cards into two columns (left: first half, right: second half)
        mid = (len(metric_cards_list) + 1) // 2
        cards_col_left = '\n'.join(metric_cards_list[:mid])
        cards_col_right = '\n'.join(metric_cards_list[mid:])

        # Build bilan rows conditionally (hide zero rows)
        def _bilan_row(icon, label, value, unit, css_class=''):
            return f'''<tr class="{css_class}">
                    <td class="bilan-icon">{icon}</td>
                    <td class="bilan-label">{label}</td>
                    <td class="bilan-value">{_fmt(value)} {unit}</td>
                </tr>'''

        def _bilan_row_if(icon, label, value, unit, css_class=''):
            """Only render row if value is non-zero."""
            if not value:
                return ''
            return _bilan_row(icon, label, value, unit, css_class)

        # Autoconsommation rows
        autocons_rows = _bilan_row('&#9889;', 'Consomm\u00e9 directement', autocons_day, 'kWh')
        autocons_rows += _bilan_row_if('&#9107;', 'Stock\u00e9 dans la batterie', battery_charge, 'kWh')
        autocons_rows += _bilan_row('&#9751;', 'Total autoconsommation', autocons_total, 'kWh', 'bilan-row-total')

        # Economies rows
        eco_rows = _bilan_row_if('&#9788;', '\u00c9conomies li\u00e9es aux panneaux', savings_panels, '&euro;')
        eco_rows += _bilan_row_if('&#9107;', '\u00c9conomies li\u00e9es \u00e0 la batterie', savings_battery, '&euro;')
        eco_rows += _bilan_row_if('&#8364;', 'Revenus de revente', savings_resale, '&euro;')

        # Build bilan card helper (uses same .card design as system section)
        def _bilan_card(icon_svg, label, value, unit):
            return f'''<div class="card">
                    <div class="card-icon">{icon_svg}</div>
                    <div class="card-text">
                        <div class="card-value">{_fmt(value)}</div>
                        <div class="card-unit">{unit}</div>
                        <div class="card-label">{label}</div>
                    </div>
                </div>'''

        # Monthly data table rows
        month_names = {
            '1': 'Janvier', '2': 'Février', '3': 'Mars', '4': 'Avril',
            '5': 'Mai', '6': 'Juin', '7': 'Juillet', '8': 'Août',
            '9': 'Septembre', '10': 'Octobre', '11': 'Novembre', '12': 'Décembre'
        }

        monthly_data_rows = ''
        daily_balance_rows = ''
        if results:
            sorted_results = results.sorted(key=lambda r: int(r.month))
            for r in sorted_results:
                mname = month_names.get(r.month, r.month)
                monthly_data_rows += f'''<tr>
                    <td>{mname}</td>
                    <td class="data-val">{r.monthly_production_kwh:,.2f}</td>
                    <td class="data-val">{r.monthly_consumption_kwh:,.2f}</td>
                    <td class="data-val">{r.daily_production_kwh:,.2f}</td>
                    <td class="data-val">{r.daily_day_consumption_kwh:,.2f}</td>
                    <td class="data-val">{r.daily_night_consumption_kwh:,.2f}</td>
                </tr>'''

                daily_balance_rows += f'''<tr>
                    <td>{mname}</td>
                    <td class="data-val">{r.daily_production_kwh:,.2f}</td>
                    <td class="data-val">{r.daily_day_consumption_kwh:,.2f}</td>
                    <td class="data-val">{r.daily_night_consumption_kwh:,.2f}</td>
                    <td class="data-val">{r.daily_battery_charge_kwh:,.2f}</td>
                    <td class="data-val">{r.daily_energy_sold_kwh:,.2f}</td>
                    <td class="data-val">{r.daily_energy_bought_kwh:,.2f}</td>
                </tr>'''

        # Location badge
        roof_badge = ''
        if simulation.roof_surface_m2:
            roof_badge = f'<div class="location-badge">{simulation.roof_surface_m2:.0f} m\u00b2</div>'

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Installation Photovolta\u00efque</title>
</head>
<body>
    <!-- Running footer for content pages -->
    <div class="running-footer">
        <span class="footer-info">{footer_line}</span>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 1: COVER PAGE                           -->
    <!-- ============================================ -->
    <div class="page cover-page">
        <!-- Full-bleed hero photo with dark overlay -->
        <div class="cover-photo-wrap">
            {f'<img src="{cover_photo_data}" alt="" class="cover-photo">' if cover_photo_data else ''}
            <div class="cover-overlay"></div>
            <div class="cover-fade"></div>
        </div>

        <!-- Logo overlaid top-left -->
        <div class="cover-logo">
            {f'<img src="{logo_data}" alt="Logo" class="logo-img">' if logo_data else ''}
        </div>

        <!-- Vertical green accent line + title block -->
        <div class="cover-title-area">
            <div class="cover-accent-line"></div>
            <div class="cover-title-block">
                <h1 class="cover-title">{cover_title}</h1>
                <h1 class="cover-title-accent">{cover_subtitle}</h1>
                {f'<p class="cover-tagline">{tagline}</p>' if tagline else ''}
            </div>
        </div>

        <!-- Client name (prominent) -->
        <div class="cover-client-area">
            {f'<p class="cover-client-name">{partner_name}</p>' if partner_name else ''}
            {f'<p class="cover-client-addr">{address.replace(chr(10), "<br/>")}</p>' if address else ''}
        </div>

        <!-- Metadata box bottom-right -->
        <div class="cover-meta-box">
            {f'<p class="cover-meta-line">R\u00e9f\u00e9rence Devis</p><p class="cover-meta-val">{project_ref}</p>' if project_ref else ''}
            {f'<p class="cover-meta-line">Date</p><p class="cover-meta-val">{report_date}</p>' if report_date else ''}
        </div>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 2: LOCALISATION                         -->
    <!-- ============================================ -->
    <div class="page content-page">
        <div class="location-page-bg">
            <div class="section-number">01</div>
            <h2 class="section-title">{title_location}</h2>

            <div class="location-image-container">
                {f'<img src="{location_image_data}" alt="Localisation" class="location-image">' if location_image_data else ''}
            </div>

            <table class="location-cards-row">
                <tr>
                    {f"""<td><div class="card">
                        <div class="card-icon">{SVG_ICON_PIN}</div>
                        <div class="card-text">
                            <div class="card-value" style="font-size:11pt;">{address.replace(chr(10), '<br/>')}</div>
                            <div class="card-label">Adresse d'installation</div>
                        </div>
                    </div></td>""" if address else ''}
                    {f"""<td><div class="card">
                        <div class="card-icon"><svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4A9B5D" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="12" y1="3" x2="12" y2="21"/></svg></div>
                        <div class="card-text">
                            <div class="card-value">{simulation.roof_surface_m2:.0f}</div>
                            <div class="card-unit">m\u00b2</div>
                            <div class="card-label">Surface de toiture</div>
                        </div>
                    </div></td>""" if simulation.roof_surface_m2 else ''}
                </tr>
            </table>
        </div>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 3: PRODUCTION (System + Chart)           -->
    <!-- ============================================ -->
    <div class="page content-page production-page">
        <div class="section">
            <div class="section-number">02</div>
            <h2 class="section-title">{title_production}</h2>

            {f'<div class="chart-container"><img src="{chart_data}" alt="Production mensuelle" class="chart-img"></div>' if chart_data else ''}
            <p class="chart-source">Production annuelle : {prod_total:,.0f} kWh/an — Source : {'PVGIS (EU Science Hub)' if simulation.pvgis_annual_production_kwh else 'Google Solar API'}</p>

            <div class="production-system-bg">
                <h3 class="section-subtitle">{title_system}</h3>

                <div class="system-container">
                    <table class="system-cards-grid">
                        <tr>
                            <td class="system-cards-col">
                                {cards_col_left}
                            </td>
                            <td class="system-cards-col">
                                {cards_col_right}
                            </td>
                        </tr>
                    </table>
                    {f'<div class="system-image-wrap"><img src="{system_image_data}" alt="" class="system-image"></div>' if system_image_data else ''}
                </div>
            </div>
        </div>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 4: DONNÉES DE CONSOMMATION              -->
    <!-- ============================================ -->
    <div class="page content-page">
        <div class="section">
            <div class="section-number">03</div>
            <h2 class="section-title">{title_consumption}</h2>
        </div>

        <!-- Section 1: Monthly/Daily Data Table -->
        <h3 class="section-subtitle">{title_monthly_data}</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Mois</th>
                    <th>Prod. Mois (kWh)</th>
                    <th>Conso. Mois (kWh)</th>
                    <th>Prod. quot. (kWh)</th>
                    <th>Conso jour (kWh)</th>
                    <th>Conso nuit (kWh)</th>
                </tr>
            </thead>
            <tbody>
                {monthly_data_rows}
            </tbody>
        </table>

        <!-- Explanation box -->
        <div class="explanation-box">
            <p>La <strong>charge</strong> est l\u2019\u00e9nergie disponible dans la batterie. Elle d\u00e9pend de la capacit\u00e9
            de la batterie et du surplus de production par rapport \u00e0 la consommation de jour.
            Elle tient \u00e9galement compte du pourcentage de batterie utilisable et de sa performance.</p>
            <p>La <strong>vente</strong> est l\u2019\u00e9nergie produite qui ne peut pas \u00eatre auto-consomm\u00e9e (ni en
            consommation de jour, ni pour charger la batterie). Elle sera alors revendue sur le r\u00e9seau.</p>
            <p>L\u2019<strong>achat</strong> correspond \u00e0 l\u2019\u00e9nergie qu\u2019il faut acheter sur le r\u00e9seau, en d\u00e9duisant
            la partie auto-consommation.</p>
        </div>

        <!-- Section 3: Daily Energy Balance Table -->
        <h3 class="section-subtitle">{title_daily_balance}</h3>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Mois</th>
                    <th>Prod. Mois (kWh)</th>
                    <th>Conso jour (kWh)</th>
                    <th>Conso nuit (kWh)</th>
                    <th>Charge (kWh)</th>
                    <th>Vente (kWh)</th>
                    <th>Achat (kWh)</th>
                </tr>
            </thead>
            <tbody>
                {daily_balance_rows}
            </tbody>
        </table>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 5: BILAN ÉNERGÉTIQUE                    -->
    <!-- ============================================ -->
    <div class="page content-page bilan-bg">
        <div class="section">
            <div class="section-number">04</div>
            <h2 class="section-title">{title_bilan}</h2>
        </div>

        <div class="bilan-content">
            <!-- Production -->
            <h3 class="section-subtitle">Production</h3>
            <table class="bilan-cards-grid">
                <tr>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_SUN, 'Production totale', prod_total, 'kWh')}</td>
                    <td class="bilan-cards-col"></td>
                    <td class="bilan-cards-col"></td>
                </tr>
            </table>

            <!-- Consommation -->
            <h3 class="section-subtitle">Consommation</h3>
            <table class="bilan-cards-grid">
                <tr>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_HOME, 'Jour', conso_day, 'kWh')}</td>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_MOON, 'Nuit', conso_night, 'kWh')}</td>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_BOLT, 'Totale', conso_total, 'kWh')}</td>
                </tr>
            </table>

            <!-- Auto Consommation -->
            <h3 class="section-subtitle">Auto Consommation</h3>
            <table class="bilan-cards-grid">
                <tr>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_RECYCLE, 'Consomm\u00e9 la journ\u00e9e', autocons_day, 'kWh')}</td>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_BATTERY, 'Stock\u00e9 dans la batterie', battery_charge, 'kWh')}</td>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_BOLT, 'Total', autocons_total, 'kWh')}</td>
                </tr>
            </table>

            <!-- \u00c9conomies -->
            <h3 class="section-subtitle">\u00c9conomies</h3>
            <table class="bilan-cards-grid">
                <tr>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_PANELS, 'Li\u00e9es aux panneaux', savings_panels, '\u20ac')}</td>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_BATTERY, 'Li\u00e9es \u00e0 la batterie', savings_battery, '\u20ac')}</td>
                    <td class="bilan-cards-col">{_bilan_card(SVG_ICON_EURO, 'Li\u00e9es \u00e0 la revente', savings_resale, '\u20ac')}</td>
                </tr>
            </table>

            <!-- Bottom summary -->
            <table class="bilan-summary-row">
                <tr>
                    <td class="bilan-summary-savings">
                        <div class="bilan-summary-savings-inner">
                            <span class="bts-icon">{SVG_ICON_PIGGY}</span>
                            <span class="bts-label">Total \u00e9conomies</span>
                            <span class="bts-value">{_fmt(savings_total)} &euro;</span>
                        </div>
                    </td>
                    <td class="bilan-summary-purchase">
                        <div class="bilan-summary-purchase-inner">
                            <span class="btp-icon">{SVG_ICON_WALLET}</span>
                            <span class="btp-label">Achat</span>
                            <span class="btp-value">{_fmt(purchase_total)} &euro;</span>
                        </div>
                    </td>
                </tr>
            </table>
        </div>
    </div>
</body>
</html>"""

        return html

    def _generate_css(self):
        """Generate CSS styling — Design System v4.0"""

        css = """
        /* ==============================================
           PHOTOVOLTAIC REPORT – DESIGN SYSTEM v4.0
           WeasyPrint-compatible (no grid, no flex-gap)
           ============================================== */

        /* ---------- Running footer ---------- */
        .running-footer {
            position: running(pageFooter);
            font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 8pt;
            color: #616161;
            text-align: left;
            padding: 1mm 0;
            width: 100%;
            line-height: 1.5;
        }

        /* ---------- @page rules ---------- */
        @page {
            size: A4;
            margin: 25mm 20mm 22mm 20mm;

            @bottom-left {
                content: element(pageFooter);
                border-top: 1.5px solid #4A9B5D;
                padding: 2mm 0 0 0;
                width: 80%;
                vertical-align: top;
            }

            @bottom-right {
                content: "Page " counter(page) " / " counter(pages);
                font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                font-size: 8pt;
                color: #616161;
                border-top: 1.5px solid #4A9B5D;
                padding-top: 3mm;
                vertical-align: top;
            }
        }

        @page :first {
            margin: 0;
            @bottom-left  { content: none; }
            @bottom-right { content: none; }
        }

        /* ---------- Reset & base ---------- */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 11pt;
            color: #212121;
            line-height: 1.55;
        }

        p { margin-bottom: 4mm; }

        strong {
            font-weight: 600;
            color: #212121;
        }

        .page {
            page-break-after: always;
        }

        /* ===================================================
           PAGE 1 – COVER
           =================================================== */
        .cover-page {
            width: 210mm;
            height: 297mm;
            position: relative;
            background: #FFFFFF;
            overflow: hidden;
        }

        /* Full-bleed photo with dark overlay */
        .cover-photo-wrap {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 175mm;
            overflow: hidden;
        }

        .cover-photo {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        /* Dark overlay on photo for contrast */
        .cover-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.18);
        }

        /* Fade from photo to white */
        .cover-fade {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 80mm;
            background: linear-gradient(
                to bottom,
                rgba(255,255,255, 0) 0%,
                rgba(255,255,255, 0.4) 35%,
                rgba(255,255,255, 0.8) 65%,
                rgba(255,255,255, 1) 100%
            );
        }

        /* Logo */
        .cover-logo {
            position: absolute;
            top: 12mm;
            left: 15mm;
            z-index: 10;
        }

        .logo-img {
            max-height: 18mm;
            max-width: 55mm;
        }

        /* Green accent line + title */
        .cover-title-area {
            position: absolute;
            top: 180mm;
            left: 20mm;
            right: 20mm;
        }

        .cover-accent-line {
            position: absolute;
            left: 0;
            top: 2mm;
            width: 3px;
            height: 42mm;
            background: #4A9B5D;
            border-radius: 2px;
        }

        .cover-title-block {
            margin-left: 12mm;
        }

        .cover-title {
            font-size: 28pt;
            font-weight: 300;
            color: #212121;
            letter-spacing: 1.5mm;
            text-transform: uppercase;
            margin: 0;
            line-height: 1.25;
        }

        .cover-title-accent {
            font-size: 28pt;
            font-weight: 300;
            color: #4A9B5D;
            letter-spacing: 1.5mm;
            text-transform: uppercase;
            margin: 0 0 4mm 0;
            line-height: 1.25;
        }

        .cover-tagline {
            font-size: 10.5pt;
            font-style: italic;
            color: #757575;
            margin: 0;
            letter-spacing: 0.2mm;
        }

        /* Client area (left side, below title) */
        .cover-client-area {
            position: absolute;
            top: 235mm;
            left: 20mm;
            right: 110mm;
        }

        .cover-client-name {
            font-size: 16pt;
            font-weight: 600;
            color: #212121;
            margin: 0 0 2mm 0;
            line-height: 1.2;
        }

        .cover-client-addr {
            font-size: 9.5pt;
            color: #616161;
            margin: 0;
            line-height: 1.4;
        }

        /* Metadata box bottom-right */
        .cover-meta-box {
            position: absolute;
            bottom: 15mm;
            right: 15mm;
            background: rgba(74, 155, 93, 0.08);
            border: 1px solid rgba(74, 155, 93, 0.25);
            border-radius: 8px;
            padding: 5mm 7mm;
            text-align: right;
            min-width: 45mm;
        }

        .cover-meta-line {
            font-size: 7.5pt;
            color: #616161;
            text-transform: uppercase;
            letter-spacing: 0.3mm;
            margin: 0;
        }

        .cover-meta-val {
            font-size: 10.5pt;
            font-weight: 600;
            color: #212121;
            margin: 0 0 2mm 0;
        }

        .cover-meta-val:last-child {
            margin-bottom: 0;
        }

        /* ===================================================
           CONTENT PAGES – Shared
           =================================================== */
        .content-page {
            padding: 0;
        }

        .production-page {
            padding: 0;
        }

        .section {
            margin-bottom: 4mm;
            page-break-inside: avoid;
        }

        .section-number {
            font-size: 28pt;
            font-weight: 700;
            color: #E0E0E0;
            float: left;
            margin-right: 4mm;
            line-height: 1;
            margin-top: -2mm;
        }

        .section-title {
            font-size: 16pt;
            font-weight: 600;
            color: #212121;
            text-transform: uppercase;
            border-bottom: 2px solid #4A9B5D;
            padding-bottom: 3mm;
            margin-bottom: 4mm;
            overflow: hidden;
            page-break-after: avoid;
        }

        .section-subtitle {
            font-size: 10pt;
            font-weight: 600;
            color: #212121;
            text-transform: uppercase;
            letter-spacing: 0.3mm;
            margin: 4mm 0 3mm 0;
        }

        .chart-source {
            text-align: center;
            font-size: 7pt;
            color: #9E9E9E;
            font-style: italic;
            margin: 1mm 0 2mm 0;
        }

        .production-system-bg {
            background: #F1F9F1;
            margin: 3mm -20mm -25mm -20mm;
            padding: 4mm 20mm 10mm 20mm;
            page-break-inside: avoid;
        }

        /* ===================================================
           PAGE 2 – LOCALISATION
           =================================================== */
        .location-page-bg {
            background: #F1F9F1;
            margin: -25mm -20mm 0 -20mm;
            padding: 25mm 20mm 6mm 20mm;
        }

        .location-image-container {
            text-align: center;
            margin: 4mm 0 6mm 0;
            page-break-inside: avoid;
        }

        .location-image {
            width: 100%;
            height: 80mm;
            object-fit: cover;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
        }

        .location-cards-row {
            width: 100%;
            border-collapse: separate;
            border-spacing: 3mm 0;
            margin: 0;
        }

        .location-cards-row td {
            width: 50%;
            vertical-align: top;
        }

        .location-cards-row .card {
            margin-bottom: 0;
        }

        /* ===================================================
           PAGE 3 – METRIC CARDS + PRODUCTION
           =================================================== */
        /* Two-column cards + image below */
        .system-container {
            border-radius: 12px;
            margin: 2mm 0 0 0;
            overflow: hidden;
            page-break-inside: avoid;
        }

        .system-cards-grid {
            width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
        }

        .system-cards-col {
            width: 50%;
            vertical-align: top;
            padding: 2mm;
        }

        .system-image-wrap {
            overflow: hidden;
            border-radius: 12px;
            margin: 3mm 0 0 0;
            max-height: 45mm;
        }

        .system-image {
            width: 100%;
            height: 45mm;
            object-fit: cover;
            display: block;
        }

        .card {
            display: block;
            width: 100%;
            margin-bottom: 2mm;
            padding: 2.5mm 3mm;
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(255, 255, 255, 0.6);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
            page-break-inside: avoid;
        }

        .card:last-child {
            margin-bottom: 0;
        }

        .card::after {
            content: '';
            display: table;
            clear: both;
        }

        .card-icon {
            float: left;
            width: 8mm;
            margin-right: 2mm;
            margin-top: 0.5mm;
        }

        .card-icon svg {
            width: 20px;
            height: 20px;
        }

        .card-text {
            overflow: hidden;
        }

        .card-value {
            font-size: 13pt;
            font-weight: 700;
            color: #212121;
            line-height: 1.1;
            display: inline;
        }

        .card-unit {
            font-size: 8pt;
            color: #616161;
            display: inline;
            margin-left: 1mm;
        }

        .card-label {
            display: block;
            font-size: 7pt;
            color: #616161;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-top: 1mm;
        }

        .chart-container {
            text-align: center;
            margin: 8mm auto 0 auto;
            page-break-inside: avoid;
        }

        .chart-img {
            max-width: 160mm;
            height: auto;
            border-radius: 6px;
        }

        /* Hero metric for annual production */
        .hero-metric {
            text-align: center;
            margin: 8mm auto;
            padding: 6mm 10mm;
            background: linear-gradient(135deg, #4A9B5D 0%, #388E3C 100%);
            border-radius: 12px;
            page-break-inside: avoid;
        }

        .hero-metric-inner {
            margin-bottom: 2mm;
        }

        .hero-metric-value {
            font-size: 32pt;
            font-weight: 700;
            color: #FFFFFF;
            letter-spacing: 0.5mm;
        }

        .hero-metric-unit {
            font-size: 14pt;
            font-weight: 400;
            color: rgba(255, 255, 255, 0.85);
            margin-left: 2mm;
        }

        .hero-metric-label {
            display: block;
            font-size: 9pt;
            color: rgba(255, 255, 255, 0.8);
            text-transform: uppercase;
            letter-spacing: 0.5mm;
        }

        /* ===================================================
           PAGE 4 – DONNÉES DE CONSOMMATION
           =================================================== */
        .consumption-bg {
            background: #F1F9F1;
            margin: -25mm -20mm -22mm -20mm;
            padding: 25mm 20mm 22mm 20mm;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 4mm;
            font-size: 8pt;
        }

        .data-table thead tr {
            background: #212121;
            color: #FFFFFF;
        }

        .data-table th {
            padding: 2mm 2.5mm;
            font-weight: 600;
            font-size: 7.5pt;
            text-align: right;
            white-space: nowrap;
        }

        .data-table th:first-child {
            text-align: left;
        }

        .data-table td {
            padding: 1.5mm 2.5mm;
            border-bottom: 0.5px solid #E0E0E0;
            font-size: 8pt;
        }

        .data-table tbody tr:nth-child(even) {
            background: #F9F9F9;
        }

        .data-val {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        .explanation-box {
            background: #F1F9F1;
            border-left: 3px solid #4A9B5D;
            border-radius: 4px;
            padding: 3mm 4mm;
            margin: 4mm 0;
            font-size: 8pt;
            line-height: 1.5;
            color: #424242;
        }

        .explanation-box p {
            margin: 0 0 1.5mm 0;
        }

        .explanation-box p:last-child {
            margin-bottom: 0;
        }

        /* ===================================================
           PAGE 5 – BILAN ÉNERGÉTIQUE (Card-based design)
           =================================================== */
        .bilan-bg {
            background: #F1F9F1;
            margin: -25mm -20mm -22mm -20mm;
            padding: 25mm 20mm 22mm 20mm;
        }

        .bilan-bg .section-subtitle {
            margin: 5mm 0 4mm 0;
            padding-bottom: 1.5mm;
            border-bottom: 1px solid #C8E6C9;
        }

        .bilan-bg .section-subtitle:first-child {
            margin-top: 0;
        }

        .bilan-cards-grid {
            width: 100%;
            table-layout: fixed;
            border-collapse: separate;
            border-spacing: 2mm 0;
        }

        .bilan-cards-col {
            width: 33.33%;
            vertical-align: top;
        }

        /* Bottom summary */
        .bilan-summary-row {
            width: 100%;
            table-layout: fixed;
            border-collapse: separate;
            border-spacing: 2mm 0;
            margin-top: 5mm;
            page-break-inside: avoid;
        }

        .bilan-summary-savings {
            width: 60%;
            vertical-align: top;
        }

        .bilan-summary-savings-inner {
            background: linear-gradient(135deg, #81C784 0%, #66BB6A 100%);
            color: #FFFFFF;
            border-radius: 10px;
            padding: 4mm 5mm;
            page-break-inside: avoid;
        }

        .bilan-summary-savings-inner::after {
            content: '';
            display: table;
            clear: both;
        }

        .bts-icon {
            float: left;
            width: 8mm;
            margin-right: 2mm;
            margin-top: 0.5mm;
        }

        .bts-icon svg {
            width: 24px;
            height: 24px;
        }

        .bts-label {
            display: block;
            font-size: 7pt;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            opacity: 0.9;
        }

        .bts-value {
            display: block;
            font-size: 14pt;
            font-weight: 700;
        }

        .bilan-summary-purchase {
            width: 40%;
            vertical-align: top;
        }

        .bilan-summary-purchase-inner {
            background: #F9F9F9;
            border: 1.5px solid #E0E0E0;
            border-radius: 10px;
            padding: 4mm 5mm;
            page-break-inside: avoid;
        }

        .bilan-summary-purchase-inner::after {
            content: '';
            display: table;
            clear: both;
        }

        .btp-icon {
            float: left;
            width: 8mm;
            margin-right: 2mm;
            margin-top: 0.5mm;
        }

        .btp-icon svg {
            width: 24px;
            height: 24px;
        }

        .btp-label {
            display: block;
            font-size: 7pt;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            color: #616161;
        }

        .btp-value {
            display: block;
            font-size: 14pt;
            font-weight: 700;
            color: #212121;
        }

        """

        return css

    def _generate_monthly_chart(self, simulation):
        """Generate monthly production bar chart with gradient bars + transparent bg"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import matplotlib.colors as mcolors
            import numpy as np
            import io
        except ImportError as e:
            _logger.warning(f"Matplotlib not available for chart generation: {e}")
            return None
        except Exception as e:
            _logger.warning(f"Matplotlib import error: {e}")
            return None

        try:
            monthly_results = simulation.monthly_result_ids.sorted(key=lambda r: r.month)
            if not monthly_results:
                return None

            months = [r.month for r in monthly_results]
            production = [r.production_pv_kwh for r in monthly_results]

            month_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
                            'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

            fig, ax = plt.subplots(figsize=(10, 3.8))
            fig.patch.set_alpha(0)
            ax.set_facecolor('none')

            # Gradient-like effect: color bars from light to dark green based on value
            max_prod = max(production) if production else 1
            colors = []
            for val in production:
                ratio = val / max_prod if max_prod else 0
                r = int(200 - ratio * 78)   # 200 -> 122 (light -> dark green)
                g = int(230 - ratio * 88)   # 230 -> 142
                b = int(201 - ratio * 141)  # 201 -> 60
                colors.append(f'#{r:02x}{g:02x}{b:02x}')

            bars = ax.bar(range(len(months)), production,
                         color=colors,
                         edgecolor='#388E3C',
                         linewidth=0.6,
                         width=0.7,
                         zorder=3)

            for bar, val in zip(bars, production):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                       f'{val:.0f}',
                       ha='center', va='bottom', fontsize=8.5,
                       fontweight='600', color='#212121')

            labels = [month_labels[m - 1] if 1 <= m <= 12 else str(m) for m in months]
            ax.set_xticks(range(len(months)))
            ax.set_xticklabels(labels, fontsize=9.5, fontweight='500', color='#616161')
            ax.set_ylabel('kWh', fontsize=10, fontweight='600', color='#616161')

            ax.grid(axis='y', alpha=0.4, linestyle='-', linewidth=0.5, color='#E0E0E0', zorder=0)
            ax.set_axisbelow(True)

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#E0E0E0')
            ax.spines['bottom'].set_linewidth(0.5)
            ax.spines['left'].set_color('#E0E0E0')
            ax.spines['left'].set_linewidth(0.5)

            ax.tick_params(axis='both', which='both', length=0,
                          labelcolor='#616161', labelsize=9.5)

            ymax = max(production) if production else 1
            ax.set_ylim(0, ymax * 1.15)

            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                       facecolor='none', edgecolor='none', transparent=True)
            buffer.seek(0)
            plt.close(fig)

            return buffer

        except Exception as e:
            _logger.error(f"Failed to generate chart: {e}")
            return None
