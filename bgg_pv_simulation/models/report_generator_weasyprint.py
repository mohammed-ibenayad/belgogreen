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
        logo_data = _make_data_uri(company.pv_report_logo or company.logo)
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
        tagline = _esc(company.pv_report_tagline or '')
        title_location = _esc(simulation.section_title_location or "LOCALISATION DE L'INSTALLATION")
        title_system = _esc(simulation.section_title_system or 'CARACTÉRISTIQUES DU SYSTÈME')
        title_production = _esc(simulation.section_title_production or 'PRODUCTION ESTIMÉE')
        title_bilan = _esc(simulation.section_title_bilan or 'BILAN ÉNERGÉTIQUE')

        # Footer
        company_name = _esc(company.name or '')
        company_phone = _esc(company.pv_report_phone or company.phone or '')
        company_email = _esc(company.pv_report_email or company.email or '')
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
        project_ref = _esc(simulation.name or '')

        # Bilan data
        results = simulation.monthly_result_ids
        prod_total = simulation.annual_production_kwh or 0.0
        conso_day = sum(results.mapped('monthly_day_consumption_kwh')) if results else 0.0
        conso_night = sum(results.mapped('monthly_night_consumption_kwh')) if results else 0.0
        conso_total = sum(results.mapped('monthly_consumption_kwh')) if results else 0.0
        if not conso_total and hasattr(simulation, 'consumption_profile_id') and simulation.consumption_profile_id:
            conso_total = simulation.consumption_profile_id.annual_consumption_kwh or 0.0
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

        # Build metric cards with SVG icons
        metric_cards = f'''
            <div class="card">
                <div class="card-icon">{SVG_ICON_SUN}</div>
                <div class="card-text">
                    <div class="card-value">{simulation.total_pv_power_wc:,.0f}</div>
                    <div class="card-unit">Wc</div>
                    <div class="card-label">Puissance install\u00e9e</div>
                </div>
            </div>'''

        if simulation.number_of_panels:
            metric_cards += f'''
            <div class="card">
                <div class="card-icon">{SVG_ICON_PANELS}</div>
                <div class="card-text">
                    <div class="card-value">{simulation.number_of_panels}</div>
                    <div class="card-unit">panneaux</div>
                    <div class="card-label">Nombre de panneaux</div>
                </div>
            </div>'''

        if simulation.orientation_deg:
            metric_cards += f'''
            <div class="card">
                <div class="card-icon">{SVG_ICON_COMPASS}</div>
                <div class="card-text">
                    <div class="card-value">{simulation.orientation_deg:.0f}\u00b0</div>
                    <div class="card-unit">&nbsp;</div>
                    <div class="card-label">Orientation</div>
                </div>
            </div>'''

        if simulation.tilt_deg:
            metric_cards += f'''
            <div class="card">
                <div class="card-icon">{SVG_ICON_TILT}</div>
                <div class="card-text">
                    <div class="card-value">{simulation.tilt_deg:.0f}\u00b0</div>
                    <div class="card-unit">&nbsp;</div>
                    <div class="card-label">Inclinaison</div>
                </div>
            </div>'''

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
            {f'<p class="cover-meta-line">R\u00e9f\u00e9rence</p><p class="cover-meta-val">{project_ref}</p>' if project_ref else ''}
            {f'<p class="cover-meta-line">Date</p><p class="cover-meta-val">{report_date}</p>' if report_date else ''}
        </div>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 2: LOCALISATION                         -->
    <!-- ============================================ -->
    <div class="page content-page">
        <div class="section">
            <div class="section-number">01</div>
            <h2 class="section-title">{title_location}</h2>

            <div class="location-block">
                {f'<p class="address-text">{address.replace(chr(10), "<br/>")}</p>' if address else ''}
            </div>

            <div class="location-image-container">
                {f'<img src="{location_image_data}" alt="Localisation" class="location-image">' if location_image_data else ''}
                <div class="location-pin">{SVG_ICON_PIN}</div>
                {roof_badge}
            </div>
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

            <h3 class="section-subtitle">{title_system}</h3>

            <div class="system-container">
                <table class="system-layout">
                    <tr>
                        <td class="system-cards-col">
                            {metric_cards}
                        </td>
                        <td class="system-image-col">
                            <div class="system-image-wrap">
                                {f'<img src="{system_image_data}" alt="" class="system-image">' if system_image_data else ''}
                                <div class="system-image-fade"></div>
                            </div>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 4: BILAN ÉNERGÉTIQUE                    -->
    <!-- ============================================ -->
    <div class="page content-page">
        <div class="section">
            <div class="section-number">03</div>
            <h2 class="section-title">{title_bilan}</h2>
        </div>

        <!-- Production (always shown) -->
        <div class="bilan-section">
            <div class="bilan-section-header">Production</div>
            <table class="bilan-table">
                {_bilan_row('&#9788;', 'Production totale annuelle', prod_total, 'kWh')}
            </table>
        </div>

        <!-- Consommation (only if data exists) -->
        {'<div class="bilan-section"><div class="bilan-section-header">Consommation</div><table class="bilan-table">' + _bilan_row('&#9788;', 'Consommation jour', conso_day, 'kWh') + _bilan_row('&#9790;', 'Consommation nuit', conso_night, 'kWh') + _bilan_row('&#9751;', 'Consommation totale', conso_total, 'kWh', 'bilan-row-total') + '</table></div>' if conso_total else ''}

        <!-- Autoconsommation (only if data exists) -->
        {'<div class="bilan-section"><div class="bilan-section-header">Autoconsommation</div><table class="bilan-table">' + autocons_rows + '</table></div>' if autocons_total else ''}

        <!-- Economies (only if data exists) -->
        {'<div class="bilan-section"><div class="bilan-section-header">' + '\u00c9conomies' + '</div><table class="bilan-table">' + eco_rows + '</table></div>' if savings_total else ''}

        <!-- Bottom summary (only if data exists) -->
        {'<div class="bilan-bottom"><div class="bilan-total-savings"><span class="bts-label">Total \u00e9conomies annuelles</span><span class="bts-value">' + _fmt(savings_total) + ' &euro;</span></div><div class="bilan-total-purchase"><span class="btp-label">Co\u00fbt d\u2019achat r\u00e9seau</span><span class="btp-value">' + _fmt(purchase_total) + ' &euro;</span></div></div>' if savings_total or purchase_total else ''}
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
            background: #F1F9F1;
            margin: -25mm -20mm;
            padding: 25mm 20mm;
        }

        .section {
            margin-bottom: 10mm;
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
            margin-bottom: 8mm;
            overflow: hidden;
            page-break-after: avoid;
        }

        .section-subtitle {
            font-size: 12pt;
            font-weight: 600;
            color: #4A9B5D;
            text-transform: uppercase;
            letter-spacing: 0.5mm;
            margin: 6mm 0 4mm 0;
        }

        /* ===================================================
           PAGE 2 – LOCALISATION
           =================================================== */
        .location-block {
            margin-bottom: 6mm;
        }

        .address-text {
            font-size: 11pt;
            color: #212121;
            margin-bottom: 3mm;
        }

        .location-image-container {
            position: relative;
            text-align: center;
            margin: 6mm auto;
            page-break-inside: avoid;
        }

        .location-image {
            width: 100%;
            max-height: 130mm;
            object-fit: cover;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
        }

        /* Location pin overlay */
        .location-pin {
            position: absolute;
            top: 50%;
            left: 50%;
            margin-top: -16px;
            margin-left: -16px;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }

        /* Roof surface badge */
        .location-badge {
            position: absolute;
            bottom: 12px;
            right: 12px;
            background: #4A9B5D;
            color: #FFFFFF;
            font-size: 9pt;
            font-weight: 600;
            padding: 2mm 4mm;
            border-radius: 20px;
            letter-spacing: 0.2mm;
        }

        /* ===================================================
           PAGE 3 – METRIC CARDS + PRODUCTION
           =================================================== */
        /* Two-column system layout */
        .system-container {
            background: #DCF0DC;
            border-radius: 16px;
            margin: 4mm 0 8mm 0;
            overflow: hidden;
        }

        .system-layout {
            width: 100%;
            border-collapse: collapse;
        }

        .system-cards-col {
            width: 45%;
            vertical-align: top;
            padding: 5mm 4mm 5mm 5mm;
        }

        .system-image-col {
            width: 55%;
            vertical-align: top;
            padding: 0;
            position: relative;
        }

        .system-image-wrap {
            position: relative;
            overflow: hidden;
        }

        .system-image {
            width: 100%;
            height: 100%;
            min-height: 60mm;
            object-fit: cover;
            display: block;
        }

        .system-image-fade {
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            width: 25mm;
            background: linear-gradient(to right, #DCF0DC 0%, rgba(220, 240, 220, 0) 100%);
        }

        .card {
            display: block;
            width: 100%;
            margin-bottom: 3mm;
            padding: 3.5mm 4mm;
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(255, 255, 255, 0.6);
            border-radius: 10px;
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
            width: 10mm;
            margin-right: 3mm;
            margin-top: 1mm;
        }

        .card-text {
            overflow: hidden;
        }

        .card-value {
            font-size: 16pt;
            font-weight: 700;
            color: #212121;
            line-height: 1.2;
            display: inline;
        }

        .card-unit {
            font-size: 9pt;
            color: #616161;
            display: inline;
            margin-left: 1mm;
        }

        .card-label {
            display: block;
            font-size: 7.5pt;
            color: #616161;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-top: 1mm;
        }

        .chart-container {
            text-align: center;
            margin: 6mm auto;
            page-break-inside: avoid;
        }

        .chart-img {
            max-width: 165mm;
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
           PAGE 4 – BILAN ÉNERGÉTIQUE
           =================================================== */
        .bilan-section {
            margin-bottom: 4mm;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            overflow: hidden;
            page-break-inside: avoid;
        }

        .bilan-section-header {
            background: #212121;
            color: #FFFFFF;
            font-size: 9pt;
            font-weight: 600;
            padding: 2mm 5mm;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .bilan-table {
            width: 100%;
            border-collapse: collapse;
        }

        .bilan-table tr {
            border-bottom: none;
        }

        /* Zebra striping */
        .bilan-table tr:nth-child(even) {
            background: #F9F9F9;
        }

        .bilan-icon {
            width: 10mm;
            text-align: center;
            font-size: 12pt;
            color: #616161;
            padding: 2.5mm 2mm;
        }

        .bilan-label {
            padding: 2.5mm 4mm;
            font-size: 10pt;
            color: #212121;
        }

        .bilan-value {
            text-align: right;
            padding: 2.5mm 5mm;
            font-size: 10pt;
            font-weight: 600;
            color: #212121;
            white-space: nowrap;
            font-variant-numeric: tabular-nums;
        }

        .bilan-row-total {
            background: #E8F5E9 !important;
        }

        .bilan-row-total .bilan-label {
            font-weight: 600;
        }

        .bilan-row-total .bilan-value {
            font-weight: 700;
            color: #388E3C;
        }

        /* Bottom summary */
        .bilan-bottom {
            margin-top: 5mm;
            page-break-inside: avoid;
        }

        .bilan-total-savings {
            display: inline-block;
            width: 48%;
            background: linear-gradient(135deg, #4A9B5D 0%, #388E3C 100%);
            color: #FFFFFF;
            border-radius: 10px;
            padding: 5mm 6mm;
            text-align: center;
            vertical-align: top;
        }

        .bts-label {
            display: block;
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            opacity: 0.9;
            margin-bottom: 2mm;
        }

        .bts-value {
            display: block;
            font-size: 18pt;
            font-weight: 700;
        }

        .bilan-total-purchase {
            display: inline-block;
            width: 48%;
            margin-left: 2%;
            background: #F9F9F9;
            border: 1.5px solid #E0E0E0;
            border-radius: 10px;
            padding: 5mm 6mm;
            text-align: center;
            vertical-align: top;
        }

        .btp-label {
            display: block;
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            color: #616161;
            margin-bottom: 2mm;
        }

        .btp-value {
            display: block;
            font-size: 18pt;
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
