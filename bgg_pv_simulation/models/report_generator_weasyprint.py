# -*- coding: utf-8 -*-
"""
PHOTOVOLTAIC REPORT DESIGN SYSTEM v3.0
WeasyPrint-based PDF Report Generator

Professional solar installation proposal report.

COLOR PALETTE:
- Primary Dark Blue: #1B3A5C  (section headings, header accents)
- Primary Green:     #4A9B5D  (savings highlights, positive values)
- Gold Accent:       #F9A825  (special highlights)
- Dark Text:         #1A1A1A  (body text)
- Gray Text:         #5F6368  (secondary text, labels)
- Light Gray BG:     #F7F8FA  (card backgrounds, alternating rows)
- Border Gray:       #E0E0E0  (borders, dividers)
- White:             #FFFFFF  (page background)

LAYOUT RULES:
- Page margins: 25mm top, 20mm sides, 22mm bottom
- Font: Inter / Helvetica / sans-serif
- Section spacing: 30px before title, 20px after
- All content blocks use page-break-inside: avoid
- WeasyPrint compatible: no flex-gap, no CSS grid, tables + inline-block only
"""

import io
import base64
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PvSimulationWeasyPrint(models.AbstractModel):
    """WeasyPrint-based PDF Report Generator - Design System v3.0"""
    _name = 'pv.simulation.weasyprint.generator'
    _description = 'WeasyPrint Report Generator for PV Simulation'

    @api.model
    def generate_report(self, simulation_id):
        """
        Generate a PDF report using WeasyPrint (HTML/CSS)

        Args:
            simulation_id: pv.simulation record ID

        Returns:
            bytes: PDF file content
        """
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

        # Generate HTML
        html_content = self._generate_html(simulation)

        # Generate CSS
        css_content = self._generate_css()

        # Create PDF
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

        # Prepare data
        partner = simulation.sale_order_id.partner_id if simulation.sale_order_id else None
        company = simulation.company_id
        user = simulation.sale_order_id.user_id if simulation.sale_order_id else None

        def _make_data_uri(b64_field):
            """Build a data URI with correct MIME type by inspecting image magic bytes."""
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
            """Escape HTML special characters to prevent XSS."""
            if not value:
                return ''
            from markupsafe import escape
            return str(escape(str(value)))

        # Encode images as base64
        logo_data = _make_data_uri(company.pv_report_logo or company.logo)
        cover_photo_data = _make_data_uri(simulation.cover_photo)
        location_image_data = _make_data_uri(simulation.location_image)
        chart_data = _make_data_uri(simulation.chart_monthly_production)

        # Generate monthly chart if not already generated
        if not chart_data and simulation.monthly_result_ids:
            try:
                chart_buffer = self._generate_monthly_chart(simulation)
                if chart_buffer:
                    chart_data = f"data:image/png;base64,{base64.b64encode(chart_buffer.getvalue()).decode()}"
            except Exception as e:
                _logger.warning(f"Could not generate chart: {e}")

        # Cover title
        cover_title = _esc(simulation.cover_title or 'Votre installation photovoltaïque')

        # Footer data
        company_name = _esc(company.name or '')
        company_phone = _esc(company.pv_report_phone or company.phone or '')
        company_email = _esc(company.pv_report_email or company.email or '')
        address = _esc(simulation.installation_address or '')

        # Salesperson info
        sp_name = _esc(user.name) if user else ''
        sp_phone = _esc(user.phone or company.phone or '') if user else company_phone
        sp_email = _esc(user.email or getattr(user, 'login', '') or '') if user else company_email

        # Footer parts
        footer_parts = []
        if company_name:
            footer_parts.append(company_name)
        if sp_phone:
            footer_parts.append(f'&#9742; {sp_phone}')
        if sp_email:
            footer_parts.append(f'&#9993; {sp_email}')
        footer_line = ' &nbsp;|&nbsp; '.join(footer_parts)

        # Partner info
        partner_name = _esc(partner.name) if partner else ''
        partner_phone = _esc(partner.phone) if partner and partner.phone else ''
        partner_email = _esc(partner.email) if partner and partner.email else ''

        # Report date
        report_date = ''
        if simulation.report_date:
            report_date = simulation.report_date.strftime('%d/%m/%Y')

        # Project reference
        project_ref = _esc(simulation.name or '')

        # ---- Bilan Annuel: aggregate monthly results ----
        results = simulation.monthly_result_ids
        # Production
        prod_total = simulation.annual_production_kwh or 0.0
        # Consumption
        conso_day = sum(results.mapped('monthly_day_consumption_kwh')) if results else 0.0
        conso_night = sum(results.mapped('monthly_night_consumption_kwh')) if results else 0.0
        conso_total = sum(results.mapped('monthly_consumption_kwh')) if results else 0.0
        if not conso_total and hasattr(simulation, 'consumption_profile_id') and simulation.consumption_profile_id:
            conso_total = simulation.consumption_profile_id.annual_consumption_kwh or 0.0
        # Auto-consumption
        autocons_total = sum(results.mapped('monthly_autoconsumption_kwh')) if results else 0.0
        battery_charge = sum(results.mapped('monthly_battery_charge_kwh')) if results else 0.0
        autocons_day = autocons_total - battery_charge
        # Savings
        savings_panels = sum(results.mapped('panel_savings')) if results else 0.0
        savings_battery = sum(results.mapped('battery_savings')) if results else 0.0
        savings_resale = sum(results.mapped('sale_revenue')) if results else 0.0
        savings_total = savings_panels + savings_battery + savings_resale
        # Purchase
        purchase_total = sum(results.mapped('purchase_cost')) if results else 0.0

        def _fmt(val):
            """Format number with 2 decimals and thousand separator, or dash if zero."""
            if not val:
                return '—'
            return f'{val:,.2f}'

        # Build client info block for cover
        client_info_rows = ''
        if partner_name:
            client_info_rows += f'<p class="client-name">{partner_name}</p>'
        if address:
            addr_lines = address.replace('\n', '<br/>')
            client_info_rows += f'<p class="client-detail">{addr_lines}</p>'
        if partner_phone:
            client_info_rows += f'<p class="client-detail">T\u00e9l\u00a0: {partner_phone}</p>'
        if partner_email:
            client_info_rows += f'<p class="client-detail">Email\u00a0: {partner_email}</p>'

        # Build metric cards for system characteristics
        metric_cards = ''
        metric_cards += f'''
            <div class="card">
                <div class="card-value">{simulation.total_pv_power_wc:,.0f}</div>
                <div class="card-unit">Wc</div>
                <div class="card-label">Puissance install\u00e9e</div>
            </div>'''

        if simulation.number_of_panels:
            metric_cards += f'''
            <div class="card">
                <div class="card-value">{simulation.number_of_panels}</div>
                <div class="card-unit">panneaux</div>
                <div class="card-label">Nombre de panneaux</div>
            </div>'''

        if simulation.orientation_deg:
            metric_cards += f'''
            <div class="card">
                <div class="card-value">{simulation.orientation_deg:.0f}\u00b0</div>
                <div class="card-unit">&nbsp;</div>
                <div class="card-label">Orientation</div>
            </div>'''

        if simulation.tilt_deg:
            metric_cards += f'''
            <div class="card">
                <div class="card-value">{simulation.tilt_deg:.0f}\u00b0</div>
                <div class="card-unit">&nbsp;</div>
                <div class="card-label">Inclinaison</div>
            </div>'''

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
        <!-- Logo top-right -->
        <div class="cover-logo">
            {f'<img src="{logo_data}" alt="Logo" class="logo-img">' if logo_data else ''}
        </div>

        <!-- Cover Photo -->
        {f'<div class="cover-photo-wrap"><img src="{cover_photo_data}" alt="" class="cover-photo"></div>' if cover_photo_data else ''}

        <!-- Main Title Block -->
        <div class="cover-title-block">
            <h1 class="cover-title">{_esc(cover_title)}</h1>
            <p class="cover-subtitle">\u00c9tude personnalis\u00e9e</p>
        </div>

        <!-- Client Info Card -->
        <div class="cover-client-card">
            <div class="cover-client-inner">
                {client_info_rows}
            </div>
            <div class="cover-meta">
                {f'<p>R\u00e9f\u00e9rence\u00a0: <strong>{project_ref}</strong></p>' if project_ref else ''}
                {f'<p>Date\u00a0: <strong>{report_date}</strong></p>' if report_date else ''}
            </div>
        </div>

        <!-- Cover Footer -->
        <div class="cover-footer">
            <div class="cover-footer-content">
                <span class="footer-company">{company_name}</span>
                {f'<span class="footer-sep">|</span><span>&#9742; {sp_phone}</span>' if sp_phone else ''}
                {f'<span class="footer-sep">|</span><span>&#9993; {sp_email}</span>' if sp_email else ''}
                {f'<br/><span class="footer-contact">{sp_name}</span>' if sp_name else ''}
            </div>
        </div>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 2: LOCALISATION                         -->
    <!-- ============================================ -->
    <div class="page content-page">
        <div class="section">
            <div class="section-number">01</div>
            <h2 class="section-title">{_esc(simulation.section_title_location or "LOCALISATION DE L'INSTALLATION")}</h2>

            <div class="location-block">
                {f'<p class="address-text">{address.replace(chr(10), "<br/>")}</p>' if address else ''}
                {f'<p>Superficie de la toiture\u00a0: <strong>{simulation.roof_surface_m2:.0f} m\u00b2</strong></p>' if simulation.roof_surface_m2 else ''}
            </div>

            {f'<div class="location-image-container"><img src="{location_image_data}" alt="Localisation" class="location-image"></div>' if location_image_data else ''}
        </div>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 3: CARACTÉRISTIQUES + PRODUCTION        -->
    <!-- ============================================ -->
    <div class="page content-page">
        <div class="section">
            <div class="section-number">02</div>
            <h2 class="section-title">CARACT\u00c9RISTIQUES DU SYST\u00c8ME</h2>

            <div class="cards-row">
                {metric_cards}
            </div>
        </div>

        <div class="section">
            <div class="section-number">03</div>
            <h2 class="section-title">{_esc(simulation.section_title_production or 'PRODUCTION ESTIM\u00c9E')}</h2>

            {f'<div class="chart-container"><img src="{chart_data}" alt="Production mensuelle" class="chart-img"></div>' if chart_data else ''}

            <div class="annual-production-highlight">
                <span class="aph-label">Production totale annuelle</span>
                <span class="aph-value">{simulation.annual_production_kwh:,.2f} kWh</span>
            </div>
        </div>
    </div>

    <!-- ============================================ -->
    <!-- PAGE 4: BILAN ÉNERGÉTIQUE                    -->
    <!-- ============================================ -->
    <div class="page content-page">
        <div class="section">
            <div class="section-number">04</div>
            <h2 class="section-title">BILAN \u00c9NERG\u00c9TIQUE</h2>
        </div>

        <!-- Production -->
        <div class="bilan-section">
            <div class="bilan-section-header">Production</div>
            <table class="bilan-table">
                <tr>
                    <td class="bilan-icon">&#9788;</td>
                    <td class="bilan-label">Production totale annuelle</td>
                    <td class="bilan-value">{_fmt(prod_total)} kWh</td>
                </tr>
            </table>
        </div>

        <!-- Consommation -->
        <div class="bilan-section">
            <div class="bilan-section-header">Consommation</div>
            <table class="bilan-table">
                <tr>
                    <td class="bilan-icon">&#9788;</td>
                    <td class="bilan-label">Consommation jour</td>
                    <td class="bilan-value">{_fmt(conso_day)} kWh</td>
                </tr>
                <tr>
                    <td class="bilan-icon">&#9790;</td>
                    <td class="bilan-label">Consommation nuit</td>
                    <td class="bilan-value">{_fmt(conso_night)} kWh</td>
                </tr>
                <tr class="bilan-row-total">
                    <td class="bilan-icon">&#9751;</td>
                    <td class="bilan-label">Consommation totale</td>
                    <td class="bilan-value">{_fmt(conso_total)} kWh</td>
                </tr>
            </table>
        </div>

        <!-- Auto Consommation -->
        <div class="bilan-section">
            <div class="bilan-section-header">Autoconsommation</div>
            <table class="bilan-table">
                <tr>
                    <td class="bilan-icon">&#9889;</td>
                    <td class="bilan-label">Consomm\u00e9 directement</td>
                    <td class="bilan-value">{_fmt(autocons_day)} kWh</td>
                </tr>
                <tr>
                    <td class="bilan-icon">&#9107;</td>
                    <td class="bilan-label">Stock\u00e9 dans la batterie</td>
                    <td class="bilan-value">{_fmt(battery_charge)} kWh</td>
                </tr>
                <tr class="bilan-row-total">
                    <td class="bilan-icon">&#9751;</td>
                    <td class="bilan-label">Total autoconsommation</td>
                    <td class="bilan-value">{_fmt(autocons_total)} kWh</td>
                </tr>
            </table>
        </div>

        <!-- Economies -->
        <div class="bilan-section">
            <div class="bilan-section-header">\u00c9conomies</div>
            <table class="bilan-table">
                <tr>
                    <td class="bilan-icon">&#9788;</td>
                    <td class="bilan-label">\u00c9conomies li\u00e9es aux panneaux</td>
                    <td class="bilan-value">{_fmt(savings_panels)} &euro;</td>
                </tr>
                <tr>
                    <td class="bilan-icon">&#9107;</td>
                    <td class="bilan-label">\u00c9conomies li\u00e9es \u00e0 la batterie</td>
                    <td class="bilan-value">{_fmt(savings_battery)} &euro;</td>
                </tr>
                <tr>
                    <td class="bilan-icon">&#8364;</td>
                    <td class="bilan-label">Revenus de revente</td>
                    <td class="bilan-value">{_fmt(savings_resale)} &euro;</td>
                </tr>
            </table>
        </div>

        <!-- Bottom summary: Total savings + Purchase -->
        <div class="bilan-bottom">
            <div class="bilan-total-savings">
                <span class="bts-label">Total \u00e9conomies annuelles</span>
                <span class="bts-value">{_fmt(savings_total)} &euro;</span>
            </div>
            <div class="bilan-total-purchase">
                <span class="btp-label">Co\u00fbt d\u2019achat r\u00e9seau</span>
                <span class="btp-value">{_fmt(purchase_total)} &euro;</span>
            </div>
        </div>
    </div>
</body>
</html>"""

        return html

    def _generate_css(self):
        """Generate CSS styling per DESIGN SYSTEM v3.0"""

        css = """
        /* ==============================================
           PHOTOVOLTAIC REPORT – DESIGN SYSTEM v3.0
           WeasyPrint-compatible (no grid, no flex-gap)
           ============================================== */

        /* ---------- Running footer (content pages) ---------- */
        .running-footer {
            position: running(pageFooter);
            font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 8pt;
            color: #5F6368;
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
                border-top: 2px solid #1B3A5C;
                padding: 2mm 0 0 0;
                width: 80%;
                vertical-align: top;
            }

            @bottom-right {
                content: "Page " counter(page) " / " counter(pages);
                font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                font-size: 8pt;
                color: #5F6368;
                border-top: 2px solid #1B3A5C;
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
            color: #1A1A1A;
            line-height: 1.55;
        }

        p { margin-bottom: 4mm; }

        strong {
            font-weight: 600;
            color: #1B3A5C;
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

        /* Decorative top band */
        .cover-page::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 8mm;
            background: #1B3A5C;
        }

        .cover-logo {
            position: absolute;
            top: 16mm;
            right: 20mm;
        }

        .logo-img {
            max-height: 22mm;
            max-width: 50mm;
        }

        .cover-photo-wrap {
            position: absolute;
            top: 48mm;
            left: 50%;
            transform: translateX(-50%);
            width: 140mm;
            height: 90mm;
            text-align: center;
        }

        .cover-photo {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 8px;
            border: 2px solid #E0E0E0;
        }

        .cover-title-block {
            position: absolute;
            top: 150mm;
            left: 20mm;
            right: 20mm;
            text-align: center;
        }

        .cover-title {
            font-size: 30pt;
            font-weight: 700;
            color: #1B3A5C;
            letter-spacing: 0.3mm;
            margin-bottom: 4mm;
            line-height: 1.2;
        }

        .cover-subtitle {
            font-size: 14pt;
            font-style: italic;
            color: #5F6368;
            margin: 0;
        }

        /* Client info card on cover */
        .cover-client-card {
            position: absolute;
            top: 195mm;
            left: 20mm;
            right: 20mm;
            border: 1px solid #E0E0E0;
            border-left: 4px solid #4A9B5D;
            border-radius: 0 6px 6px 0;
            padding: 6mm 8mm;
            background: #F7F8FA;
        }

        .cover-client-inner {
            display: inline-block;
            vertical-align: top;
            width: 58%;
        }

        .cover-meta {
            display: inline-block;
            vertical-align: top;
            width: 38%;
            text-align: right;
        }

        .cover-meta p {
            margin-bottom: 2mm;
            font-size: 10pt;
            color: #5F6368;
        }

        .cover-meta strong {
            color: #1A1A1A;
        }

        .client-name {
            font-size: 14pt;
            font-weight: 600;
            color: #1A1A1A;
            margin-bottom: 2mm;
        }

        .client-detail {
            font-size: 10pt;
            color: #5F6368;
            margin-bottom: 1mm;
        }

        /* Cover footer */
        .cover-footer {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: #1B3A5C;
            padding: 4mm 20mm;
        }

        .cover-footer-content {
            font-size: 8.5pt;
            color: #FFFFFF;
            text-align: center;
            line-height: 1.7;
        }

        .footer-company {
            font-weight: 600;
        }

        .footer-sep {
            margin: 0 2mm;
            opacity: 0.6;
        }

        .footer-contact {
            font-style: italic;
            opacity: 0.8;
        }

        /* ===================================================
           CONTENT PAGES – Shared
           =================================================== */
        .content-page {
            padding: 0;
        }

        .section {
            margin-bottom: 12mm;
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
            font-size: 18pt;
            font-weight: 600;
            color: #1B3A5C;
            text-transform: uppercase;
            border-bottom: 2px solid #E0E0E0;
            padding-bottom: 3mm;
            margin-bottom: 8mm;
            overflow: hidden;
            page-break-after: avoid;
        }

        /* ===================================================
           PAGE 2 – LOCALISATION
           =================================================== */
        .location-block {
            margin-bottom: 8mm;
        }

        .address-text {
            font-size: 11pt;
            color: #1A1A1A;
            margin-bottom: 3mm;
        }

        .location-image-container {
            text-align: center;
            margin: 8mm auto;
            padding: 6mm;
            background: #F7F8FA;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            page-break-inside: avoid;
        }

        .location-image {
            width: 75%;
            max-height: 120mm;
            object-fit: cover;
            border-radius: 4px;
        }

        /* ===================================================
           PAGE 3 – METRIC CARDS + PRODUCTION
           =================================================== */
        .cards-row {
            text-align: center;
            margin: 6mm 0 10mm 0;
        }

        .card {
            display: inline-block;
            vertical-align: top;
            width: 23%;
            margin: 0 0.8%;
            text-align: center;
            padding: 6mm 3mm;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            background: #F7F8FA;
            page-break-inside: avoid;
        }

        .card-value {
            font-size: 22pt;
            font-weight: 700;
            color: #1B3A5C;
            line-height: 1.2;
        }

        .card-unit {
            font-size: 10pt;
            color: #5F6368;
            margin-bottom: 2mm;
        }

        .card-label {
            font-size: 9pt;
            color: #5F6368;
            text-transform: uppercase;
            letter-spacing: 0.3px;
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

        /* Annual production highlight */
        .annual-production-highlight {
            text-align: center;
            margin: 8mm auto;
            padding: 5mm 10mm;
            background: #F7F8FA;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            page-break-inside: avoid;
        }

        .aph-label {
            display: block;
            font-size: 10pt;
            color: #5F6368;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-bottom: 2mm;
        }

        .aph-value {
            display: block;
            font-size: 22pt;
            font-weight: 700;
            color: #4A9B5D;
        }

        /* ===================================================
           PAGE 4 – BILAN ÉNERGÉTIQUE
           =================================================== */
        .bilan-section {
            margin-bottom: 5mm;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            overflow: hidden;
            page-break-inside: avoid;
        }

        .bilan-section-header {
            background: #1B3A5C;
            color: #FFFFFF;
            font-size: 10pt;
            font-weight: 600;
            padding: 2.5mm 5mm;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        .bilan-table {
            width: 100%;
            border-collapse: collapse;
        }

        .bilan-table tr {
            border-bottom: 1px solid #F0F0F0;
        }

        .bilan-table tr:last-child {
            border-bottom: none;
        }

        .bilan-icon {
            width: 10mm;
            text-align: center;
            font-size: 12pt;
            color: #5F6368;
            padding: 3mm 2mm;
        }

        .bilan-label {
            padding: 3mm 4mm;
            font-size: 10pt;
            color: #1A1A1A;
        }

        .bilan-value {
            text-align: right;
            padding: 3mm 5mm;
            font-size: 10pt;
            font-weight: 600;
            color: #1A1A1A;
            white-space: nowrap;
        }

        .bilan-row-total {
            background: #F7F8FA;
        }

        .bilan-row-total .bilan-label {
            font-weight: 600;
        }

        .bilan-row-total .bilan-value {
            font-weight: 700;
            color: #1B3A5C;
        }

        /* Bottom summary row */
        .bilan-bottom {
            margin-top: 6mm;
            page-break-inside: avoid;
        }

        .bilan-total-savings {
            display: inline-block;
            width: 48%;
            background: #4A9B5D;
            color: #FFFFFF;
            border-radius: 8px;
            padding: 5mm 6mm;
            text-align: center;
            vertical-align: top;
        }

        .bts-label {
            display: block;
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            opacity: 0.9;
            margin-bottom: 2mm;
        }

        .bts-value {
            display: block;
            font-size: 20pt;
            font-weight: 700;
        }

        .bilan-total-purchase {
            display: inline-block;
            width: 48%;
            margin-left: 2%;
            background: #F7F8FA;
            border: 2px solid #E0E0E0;
            border-radius: 8px;
            padding: 5mm 6mm;
            text-align: center;
            vertical-align: top;
        }

        .btp-label {
            display: block;
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            color: #5F6368;
            margin-bottom: 2mm;
        }

        .btp-value {
            display: block;
            font-size: 20pt;
            font-weight: 700;
            color: #1A1A1A;
        }
        """

        return css

    def _generate_monthly_chart(self, simulation):
        """Generate monthly production bar chart using matplotlib"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import io
        except ImportError as e:
            _logger.warning(f"Matplotlib not available for chart generation: {e}")
            return None
        except Exception as e:
            _logger.warning(f"Matplotlib import error: {e}")
            return None

        try:
            # Get monthly data
            monthly_results = simulation.monthly_result_ids.sorted(key=lambda r: r.month)

            if not monthly_results:
                return None

            months = [r.month for r in monthly_results]
            production = [r.production_pv_kwh for r in monthly_results]

            # Month labels (French)
            month_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
                            'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

            # Create figure
            fig, ax = plt.subplots(figsize=(10, 3.8))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('#FFFFFF')

            bars = ax.bar(range(len(months)), production,
                         color='#4A9B5D',
                         edgecolor='#3A8B4D',
                         linewidth=0.8,
                         width=0.7,
                         zorder=3)

            # Add value labels on bars
            for bar, val in zip(bars, production):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                       f'{val:.0f}',
                       ha='center', va='bottom', fontsize=8.5,
                       fontweight='600', color='#1A1A1A')

            # Styling
            labels = [month_labels[m - 1] if 1 <= m <= 12 else str(m) for m in months]
            ax.set_xticks(range(len(months)))
            ax.set_xticklabels(labels, fontsize=9.5, fontweight='500', color='#5F6368')
            ax.set_ylabel('kWh', fontsize=10, fontweight='600', color='#5F6368')

            # Grid
            ax.grid(axis='y', alpha=0.5, linestyle='-', linewidth=0.5, color='#E0E0E0', zorder=0)
            ax.set_axisbelow(True)

            # Spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#E0E0E0')
            ax.spines['bottom'].set_linewidth(0.5)
            ax.spines['left'].set_color('#E0E0E0')
            ax.spines['left'].set_linewidth(0.5)

            ax.tick_params(axis='both', which='both', length=0,
                          labelcolor='#5F6368', labelsize=9.5)

            # Add some padding at top for value labels
            ymax = max(production) if production else 1
            ax.set_ylim(0, ymax * 1.15)

            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                       facecolor='white', edgecolor='none', transparent=False)
            buffer.seek(0)
            plt.close(fig)

            return buffer

        except Exception as e:
            _logger.error(f"Failed to generate chart: {e}")
            return None
