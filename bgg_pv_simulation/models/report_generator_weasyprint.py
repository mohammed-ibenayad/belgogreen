# -*- coding: utf-8 -*-
"""
PHOTOVOLTAIC REPORT DESIGN SYSTEM v2.0
WeasyPrint-based PDF Report Generator

This module implements the complete design system for photovoltaic installation reports.
All colors, spacing, typography, and layout rules follow the v2.0 design specification.

COLOR PALETTE:
- Primary Green:    #4A9B5D  (headings, CTAs, chart bars)
- Primary Dark:     #2D7A4F  (emphasis, data highlights)
- Primary Light:    #6BB87A  (secondary elements, icons)
- Gold Accent:      #F9A825  (highlights, underlines)
- Dark Text:        #1A1A1A  (body text)
- Gray Text:        #5F6368  (secondary text, headers, footers)
- Light Gray:       #F5F5F5  (backgrounds, footer)
- Border Gray:      #E0E0E0  (borders, dividers)

LAYOUT RULES:
- Page margins: 25mm top, 20mm sides and bottom
- Header: white background, gray text, subtle border
- Footer: light gray background (#F5F5F5), NOT dark green (except cover)
- Section spacing: 15mm before, 12mm after underline
- All content blocks use page-break-inside: avoid
"""

import io
import base64
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PvSimulationWeasyPrint(models.AbstractModel):
    """WeasyPrint-based PDF Report Generator - Design System v2.0"""
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

        # Strip trailing "PHOTOVOLTAÏQUE" from cover_title so it doesn't duplicate
        # the hardcoded second title line in the template
        raw_cover_title = simulation.cover_title or 'VOTRE INSTALLATION'
        cover_title_line1 = raw_cover_title.replace(' PHOTOVOLTAÏQUE', '').replace('PHOTOVOLTAÏQUE', '').strip()

        # Footer data
        company_name = _esc(company.name or '')
        company_street = _esc(company.street or '')
        company_zip = _esc(company.zip or '')
        company_city = _esc(company.city or '')
        company_email = _esc(company.pv_report_email or company.email or '')
        company_phone = _esc(company.pv_report_phone or company.phone or '')
        address = _esc(simulation.installation_address or '')

        # Footer line 1: Company Name | Address
        address_str = f"{company_street} {company_zip} {company_city}".strip()
        footer_line1 = ' | '.join(filter(None, [company_name, address_str]))

        # Salesperson info for footer line 2 (with icons)
        sp_name = _esc(user.name) if user else ''
        sp_phone = _esc(user.phone or company.phone or '') if user else company_phone
        sp_email = _esc(user.email or getattr(user, 'login', '') or '') if user else company_email
        footer_line2_parts = []
        if sp_name:
            footer_line2_parts.append(sp_name)
        if sp_phone:
            footer_line2_parts.append(f'&#9742; {sp_phone}')
        if sp_email:
            footer_line2_parts.append(f'&#9993; {sp_email}')
        footer_line2 = '&nbsp;&nbsp;&nbsp;'.join(footer_line2_parts)

        # Partner info
        partner_name = _esc(partner.name) if partner else ''
        partner_phone = _esc(partner.phone) if partner and partner.phone else ''
        partner_email = _esc(partner.email) if partner and partner.email else ''
        partner_contact_parts = []
        if partner_phone:
            partner_contact_parts.append(f"Tél: {partner_phone}")
        if partner_email:
            partner_contact_parts.append(f"Email: {partner_email}")
        partner_contact_line = ' | '.join(partner_contact_parts)

        # ---- Bilan Annuel: aggregate monthly results ----
        results = simulation.monthly_result_ids
        # Production
        prod_total = simulation.annual_production_kwh or 0.0
        # Consumption (from monthly results or consumption profile)
        conso_day = sum(results.mapped('monthly_day_consumption_kwh')) if results else 0.0
        conso_night = sum(results.mapped('monthly_night_consumption_kwh')) if results else 0.0
        conso_total = sum(results.mapped('monthly_consumption_kwh')) if results else 0.0
        if not conso_total and hasattr(simulation, 'consumption_profile_id') and simulation.consumption_profile_id:
            conso_total = simulation.consumption_profile_id.annual_consumption_kwh or 0.0
        # Auto-consumption
        autocons_total = sum(results.mapped('monthly_autoconsumption_kwh')) if results else 0.0
        battery_charge = sum(results.mapped('monthly_battery_charge_kwh')) if results else 0.0
        autocons_day = autocons_total - battery_charge
        # Economies
        savings_panels = sum(results.mapped('panel_savings')) if results else 0.0
        savings_battery = sum(results.mapped('battery_savings')) if results else 0.0
        savings_resale = sum(results.mapped('sale_revenue')) if results else 0.0
        savings_total = savings_panels + savings_battery + savings_resale
        # Achat
        purchase_total = sum(results.mapped('purchase_cost')) if results else 0.0

        def _fmt(val):
            """Format number with 2 decimals and thousand separator, or dash if zero."""
            if not val:
                return '—'
            return f'{val:,.2f}'

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Installation Photovoltaïque</title>
</head>
<body>
    <!-- Running footer for content pages (placed in @page margin by CSS) -->
    <div class="running-footer">
        <div class="footer-row">
            <span class="footer-info">{footer_line1}</span>
        </div>
        <div class="footer-row">
            <span class="footer-info">{footer_line2}</span>
        </div>
    </div>

    <!-- Page 1: Cover Page -->
    <div class="page cover-page">
        <!-- Logo -->
        <div class="logo-container">
            {f'<img src="{logo_data}" alt="Logo" class="logo">' if logo_data else ''}
        </div>

        <!-- Decorative blobs -->
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>

        <!-- Cover Photo -->
        <div class="cover-photo-container">
            {f'<img src="{cover_photo_data}" alt="Cover Photo" class="cover-photo">' if cover_photo_data else ''}
        </div>

        <!-- Main Title -->
        <div class="main-title">
            <h1 class="title-line1">{_esc(cover_title_line1)}</h1>
            <h1 class="title-line2">PHOTOVOLTAÏQUE</h1>
            <p class="tagline">{_esc(company.pv_report_tagline or 'Save your planet. Save your wallet.')}</p>
        </div>

        <!-- Cover Footer (same as content footer, no page number) -->
        <div class="cover-footer">
            <div class="cover-footer-inner">
                <span class="footer-info">{footer_line1}</span>
                <br/>
                <span class="footer-info">{footer_line2}</span>
            </div>
        </div>
    </div>

    <!-- Page 2: Location -->
    <div class="page content-page">
        <div class="section">
            <h2 class="section-title">{_esc(simulation.section_title_location or "LOCALISATION DE L'INSTALLATION")}</h2>
            <div class="section-underline"></div>

            <div class="location-info">
                {f'<p class="address">{address}</p>' if address else ''}
                {f'<p>Superficie de la toiture : <strong>{simulation.roof_surface_m2:.0f} m²</strong></p>' if simulation.roof_surface_m2 else ''}
            </div>

            {f'<div class="location-image-container"><img src="{location_image_data}" alt="Location" class="location-image"></div>' if location_image_data else ''}
        </div>
    </div>

    <!-- Page 3: Production -->
    <div class="page content-page">
        <div class="section">
            <h2 class="section-title">{_esc(simulation.section_title_production or 'PRODUCTION MOYENNE JOURNALIÈRE')}</h2>
            <div class="section-underline"></div>

            <div class="production-stats">
                <div class="stats-content">
                    <p>Puissance panneaux : <strong>{simulation.total_pv_power_wc:,.0f} Wc</strong></p>
                    {f'<p>Orientation : <strong>{simulation.orientation_deg:.0f}°</strong></p>' if simulation.orientation_deg else ''}
                    {f'<p>Inclinaison : <strong>{simulation.tilt_deg:.0f}°</strong></p>' if simulation.tilt_deg else ''}
                </div>
            </div>

            {f'<div class="chart-container"><img src="{chart_data}" alt="Production Chart" class="chart"></div>' if chart_data else ''}

            <p class="annual-total">Production totale annuelle : <strong>{simulation.annual_production_kwh:,.2f} kWh</strong></p>
        </div>
    </div>

    <!-- Page 4: Bilan Annuel -->
    <div class="page content-page">
        <h2 class="section-title">BILAN ANNUEL</h2>
        <div class="section-underline"></div>

        <div class="bilan-dashboard">
            <!-- Row 1: Production + Consommation -->
            <div class="bilan-row">
                <div class="bilan-cell bilan-prod">
                    <div class="bilan-cell-header">Production</div>
                    <div class="bilan-cell-icon">&#9788;</div>
                    <div class="bilan-cell-label">Totale</div>
                    <div class="bilan-cell-value">{_fmt(prod_total)} kWh</div>
                </div>
                <div class="bilan-cell bilan-conso-group">
                    <div class="bilan-cell-header">Consommation</div>
                    <div class="bilan-trio">
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#9788;</div>
                            <div class="bilan-cell-label">Jour</div>
                            <div class="bilan-cell-value">{_fmt(conso_day)} kWh</div>
                        </div>
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#9790;</div>
                            <div class="bilan-cell-label">Nuit</div>
                            <div class="bilan-cell-value">{_fmt(conso_night)} kWh</div>
                        </div>
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#9751;</div>
                            <div class="bilan-cell-label">Totale</div>
                            <div class="bilan-cell-value">{_fmt(conso_total)} kWh</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Row 2: Auto Consommation -->
            <div class="bilan-row">
                <div class="bilan-cell bilan-full-row">
                    <div class="bilan-cell-header">Auto Consommation</div>
                    <div class="bilan-trio">
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#9889;</div>
                            <div class="bilan-cell-label">Consommé la journée</div>
                            <div class="bilan-cell-value">{_fmt(autocons_day)} kWh</div>
                        </div>
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#9107;</div>
                            <div class="bilan-cell-label">Stocké dans la batterie</div>
                            <div class="bilan-cell-value">{_fmt(battery_charge)} kWh</div>
                        </div>
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#9751;</div>
                            <div class="bilan-cell-label">Total</div>
                            <div class="bilan-cell-value">{_fmt(autocons_total)} kWh</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Row 3: Economies -->
            <div class="bilan-row">
                <div class="bilan-cell bilan-full-row">
                    <div class="bilan-cell-header">Economies</div>
                    <div class="bilan-trio">
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#9788;</div>
                            <div class="bilan-cell-label">Liées aux panneaux</div>
                            <div class="bilan-cell-value">{_fmt(savings_panels)} &euro;</div>
                        </div>
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#9107;</div>
                            <div class="bilan-cell-label">Liées à la batterie</div>
                            <div class="bilan-cell-value">{_fmt(savings_battery)} &euro;</div>
                        </div>
                        <div class="bilan-trio-item">
                            <div class="bilan-cell-icon">&#8364;</div>
                            <div class="bilan-cell-label">Liées à la revente</div>
                            <div class="bilan-cell-value">{_fmt(savings_resale)} &euro;</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Row 4: Total economies + Achat -->
            <div class="bilan-bottom-row">
                <div class="bilan-bottom-cell bilan-savings-total">
                    <span class="bilan-bottom-label">Total économies</span>
                    <span class="bilan-bottom-value">{_fmt(savings_total)}&euro;</span>
                </div>
                <div class="bilan-bottom-cell bilan-purchase">
                    <span class="bilan-bottom-label">Achat</span>
                    <span class="bilan-bottom-value">{_fmt(purchase_total)}&euro;</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""

        return html

    def _generate_css(self):
        """Generate CSS styling per DESIGN SYSTEM v2.0"""

        css = """
        /* PHOTOVOLTAIC REPORT DESIGN SYSTEM v3.1
           Primary Green #4A9B5D: cover titles, lines, accents
           Black #1A1A1A: content page titles */

        /* Running footer for content pages */
        .running-footer {
            position: running(pageFooter);
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            font-size: 8pt;
            color: #5F6368;
            text-align: left;
            padding: 1mm 0;
            width: 100%;
        }

        .footer-row {
            margin: 0.5mm 0;
            line-height: 1.4;
        }

        /* ===== PAGE RULES ===== */
        @page {
            size: A4;
            margin: 15mm 20mm 20mm 20mm;

            @bottom-left {
                content: element(pageFooter);
                border-top: 2px solid #4A9B5D;
                padding: 2mm 0 0 0;
                width: 85%;
                vertical-align: top;
            }

            @bottom-right {
                content: "Page " counter(page) " / " counter(pages);
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 8pt;
                color: #5F6368;
                border-top: 2px solid #4A9B5D;
                padding-top: 3mm;
                vertical-align: top;
            }
        }

        @page :first {
            margin: 0;
            @bottom-left { content: none; }
            @bottom-right { content: none; }
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 11pt;
            color: #1A1A1A;
            line-height: 1.5;
        }

        .page {
            page-break-after: always;
        }

        /* ===== COVER PAGE (original light background) ===== */
        .cover-page {
            width: 210mm;
            height: 297mm;
            position: relative;
            background: linear-gradient(135deg, #FAFAFA 0%, #F5F5F5 100%);
            overflow: hidden;
        }

        .content-page {
            padding: 0;
        }

        .logo-container {
            position: absolute;
            top: 20mm;
            right: 20mm;
            width: 40mm;
            height: 40mm;
        }

        .logo {
            max-width: 100%;
            max-height: 100%;
        }

        /* Decorative blobs */
        .blob {
            position: absolute;
            background: #E8F5E9;
            border-radius: 50%;
            opacity: 0.6;
        }

        .blob-1 {
            width: 160mm;
            height: 160mm;
            top: 40mm;
            left: -30mm;
        }

        .blob-2 {
            width: 120mm;
            height: 120mm;
            top: 60mm;
            right: -20mm;
        }

        .cover-photo-container {
            position: absolute;
            top: 55mm;
            left: 50%;
            transform: translateX(-50%);
            width: 130mm;
            height: 95mm;
        }

        .cover-photo {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 12px;
            border: 3px solid #4A9B5D;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        }

        .main-title {
            position: absolute;
            top: 160mm;
            width: 100%;
            text-align: center;
        }

        .title-line1,
        .title-line2 {
            color: #1A1A1A;
            font-size: 28pt;
            font-weight: 700;
            letter-spacing: 0.5mm;
        }

        .title-line1 {
            margin-bottom: 3mm;
        }

        .title-line2 {
            margin-bottom: 6mm;
        }

        .tagline {
            color: #666;
            font-size: 12pt;
            font-style: italic;
        }

        /* Cover footer: matches content footer style, no page number */
        .cover-footer {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 4mm 20mm;
            border-top: 2px solid #4A9B5D;
            background: #FFFFFF;
        }

        .cover-footer-inner {
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            font-size: 8pt;
            color: #5F6368;
            text-align: left;
            line-height: 1.6;
        }

        /* ===== CONTENT PAGES ===== */
        .section {
            margin-bottom: 15mm;
            page-break-inside: avoid;
        }

        /* Content page titles: black */
        .section-title {
            color: #1A1A1A;
            font-size: 20pt;
            font-weight: 600;
            margin-top: 0;
            margin-bottom: 4mm;
            page-break-after: avoid;
        }

        /* Horizontal underline - green */
        .section-underline {
            width: 60px;
            height: 3px;
            background: #4A9B5D;
            margin-bottom: 10mm;
            border: none;
        }

        .location-info {
            margin-bottom: 8mm;
        }

        .address {
            font-size: 11pt;
            margin-bottom: 4mm;
            color: #1A1A1A;
        }

        p {
            margin-bottom: 4mm;
            color: #1A1A1A;
        }

        strong {
            font-weight: 600;
            color: #4A9B5D;
        }

        /* Location image: rectangular, bigger, decorative border with pattern background */
        .location-image-container {
            text-align: center;
            margin: 10mm auto;
            padding: 12mm;
            background:
                radial-gradient(circle at 20px 20px, rgba(74, 155, 93, 0.04) 2px, transparent 2px),
                radial-gradient(circle at 60px 60px, rgba(74, 155, 93, 0.03) 2px, transparent 2px),
                linear-gradient(135deg, #F8FBF9 0%, #F0F7F2 100%);
            background-size: 40px 40px, 40px 40px, 100% 100%;
            border: 2px solid #4A9B5D;
            border-radius: 10px;
            page-break-inside: avoid;
        }

        .location-image {
            width: 70%;
            max-height: 112mm;
            object-fit: cover;
            border-radius: 6px;
            border: 1px solid #E0E0E0;
        }

        /* Vertical line (border-left) - green */
        .production-stats {
            background: #F9F9F9;
            border-left: 4px solid #4A9B5D;
            border-radius: 0 8px 8px 0;
            padding: 8mm 15mm;
            margin: 8mm 0;
            page-break-inside: avoid;
        }

        .stats-content p {
            margin: 3mm 0;
            font-size: 11pt;
            line-height: 1.5;
        }

        .chart-container {
            text-align: center;
            margin: 10mm auto;
            page-break-inside: avoid;
        }

        .chart {
            max-width: 170mm;
            height: auto;
            border-radius: 8px;
        }

        /* Annual total: plain text, no background */
        .annual-total {
            text-align: center;
            font-size: 13pt;
            margin: 8mm auto;
            color: #1A1A1A;
        }

        .annual-total strong {
            font-weight: 700;
            color: #1A1A1A;
        }

        /* ===== BILAN ANNUEL DASHBOARD ===== */
        .bilan-dashboard {
            background: #2D2D2D;
            border-radius: 10px;
            padding: 6mm;
            color: #FFFFFF;
            page-break-inside: avoid;
        }

        .bilan-row {
            display: flex;
            gap: 3mm;
            margin-bottom: 3mm;
        }

        .bilan-cell {
            background: #3A3A3A;
            border-radius: 8px;
            padding: 5mm;
            text-align: center;
        }

        .bilan-prod {
            width: 28%;
        }

        .bilan-conso-group {
            width: 72%;
        }

        .bilan-full-row {
            width: 100%;
        }

        .bilan-cell-header {
            color: #C8E84A;
            font-size: 11pt;
            font-weight: 600;
            margin-bottom: 4mm;
            text-align: center;
        }

        .bilan-cell-icon {
            font-size: 18pt;
            color: #FFFFFF;
            opacity: 0.7;
            margin-bottom: 2mm;
        }

        .bilan-cell-label {
            font-size: 8pt;
            color: #BBBBBB;
            margin-bottom: 1mm;
        }

        .bilan-cell-value {
            font-size: 10pt;
            font-weight: 700;
            color: #C8E84A;
        }

        .bilan-trio {
            display: flex;
            justify-content: space-around;
        }

        .bilan-trio-item {
            text-align: center;
            flex: 1;
            padding: 0 2mm;
        }

        /* Bottom row: Total economies + Achat */
        .bilan-bottom-row {
            display: flex;
            gap: 3mm;
            margin-top: 3mm;
        }

        .bilan-bottom-cell {
            border-radius: 8px;
            padding: 4mm 8mm;
            display: flex;
            align-items: center;
            gap: 4mm;
        }

        .bilan-savings-total {
            background: #C8E84A;
            color: #1A1A1A;
            flex: 1;
        }

        .bilan-purchase {
            background: #C8E84A;
            color: #1A1A1A;
            flex: 1;
        }

        .bilan-bottom-label {
            font-size: 10pt;
            font-weight: 600;
        }

        .bilan-bottom-value {
            font-size: 12pt;
            font-weight: 700;
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
            month_labels = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

            # Create figure with design system styling
            fig, ax = plt.subplots(figsize=(10, 4))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('#FFFFFF')

            # Create bars with gradient effect using design system colors
            # Bar Gradient: Bottom #81C784 → Top #4A9B5D
            from matplotlib.colors import LinearSegmentedColormap
            import matplotlib.patches as mpatches

            # Create gradient colormap from design system
            cmap = LinearSegmentedColormap.from_list(
                'green_gradient',
                ['#81C784', '#4A9B5D']  # Bottom to Top
            )

            bars = ax.bar(range(len(months)), production,
                         color='#4A9B5D',  # Solid color for compatibility
                         edgecolor='#2D7A4F',
                         linewidth=1.2,
                         width=0.75)

            # Apply gradient to each bar and add value labels
            for i, (bar, val) in enumerate(zip(bars, production)):
                # Apply gradient color from design system
                bar.set_facecolor('#6BB87A')  # Mid-gradient approximation
                bar.set_edgecolor('#2D7A4F')

                # Add value labels on bars
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{val:.1f}',
                       ha='center', va='bottom', fontsize=9,
                       fontweight='600', color='#1A1A1A')

            # Styling per design system
            ax.set_xticks(range(len(months)))
            ax.set_xticklabels(month_labels, fontsize=10, fontweight='500', color='#5F6368')
            ax.set_ylabel('kWh', fontsize=11, fontweight='600', color='#5F6368')

            # Grid lines per design system: #E0E0E0
            ax.grid(axis='y', alpha=1.0, linestyle='-', linewidth=0.5, color='#E0E0E0')
            ax.set_axisbelow(True)

            # Remove borders/spines for clean look
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#E0E0E0')
            ax.spines['bottom'].set_linewidth(0.5)
            ax.spines['left'].set_color('#E0E0E0')
            ax.spines['left'].set_linewidth(0.5)

            # Style tick parameters per design system
            ax.tick_params(axis='both', which='both', length=0, labelcolor='#5F6368', labelsize=10)

            plt.tight_layout()

            # Save to buffer (transparent background, no frame)
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                       facecolor='white', edgecolor='none', transparent=False)
            buffer.seek(0)
            plt.close(fig)

            return buffer

        except Exception as e:
            _logger.error(f"Failed to generate chart: {e}")
            return None
