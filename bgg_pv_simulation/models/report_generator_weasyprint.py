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

        # Encode images as base64
        logo_data = _make_data_uri(company.pv_report_logo)
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

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Installation Photovoltaïque</title>
        </head>
        <body>
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
                    <h1 class="title-green">{cover_title_line1}</h1>
                    <h1 class="title-black">PHOTOVOLTAÏQUE</h1>
                    <p class="tagline">{company.pv_report_tagline or 'Save your planet. Save your wallet.'}</p>
                </div>

                <!-- Customer Info Box -->
                <div class="customer-box">
                    <div class="customer-box-border"></div>
                    <div class="customer-content">
                        <h3>CLIENT</h3>
                        {f'<p class="customer-name">{partner.name}</p>' if partner else ''}
                        {f'<p class="customer-contact">Tél: {partner.phone} | Email: {partner.email}</p>' if partner and (partner.phone or partner.email) else ''}
                        {f'<p>Adresse: {simulation.installation_address}</p>' if simulation.installation_address else ''}
                    </div>
                </div>

                <!-- Footer -->
                <div class="footer-wave">
                    <div class="footer-content">
                        <p><strong>{company.name}</strong></p>
                        <p>{company.street} - {company.zip} {company.city}</p>
                        {f'<p>{user.name} | Tél: {user.phone or company.phone} | {user.email or user.login or ""}</p>' if user else f'<p>{company.phone}</p>'}
                        {f'<p>TVA: {company.vat}</p>' if company.vat else ''}
                    </div>
                </div>
            </div>

            <!-- Page 2: Location & Production -->
            <div class="page location-page">
                <!-- Section: Location -->
                <div class="section">
                    <h2 class="section-title">LOCALISATION DE L'INSTALLATION</h2>
                    <div class="section-underline"></div>

                    <div class="location-info">
                        {f'<p class="address">{simulation.installation_address}</p>' if simulation.installation_address else ''}
                        {f'<p>Superficie de la toiture : <strong>{simulation.roof_surface_m2:.0f} m²</strong></p>' if simulation.roof_surface_m2 else ''}
                    </div>

                    {f'<div class="location-image-container"><img src="{location_image_data}" alt="Location" class="location-image"></div>' if location_image_data else ''}
                </div>

                <!-- Section: Production (keep chart + stats + total together) -->
                <div class="section production-section">
                    <h2 class="section-title">PRODUCTION MOYENNE JOURNALIÈRE</h2>
                    <div class="section-underline"></div>

                    <div class="production-stats">
                        <div class="stats-sidebar"></div>
                        <div class="stats-content">
                            <p>Puissance panneaux : <strong>{simulation.total_pv_power_wc:.0f} Wc</strong></p>
                            {f'<p>Orientation : <strong>{simulation.orientation_deg:.0f}°</strong></p>' if simulation.orientation_deg else ''}
                            {f'<p>Inclinaison : <strong>{simulation.tilt_deg:.0f}°</strong></p>' if simulation.tilt_deg else ''}
                        </div>
                    </div>

                    {f'<div class="chart-container"><img src="{chart_data}" alt="Production Chart" class="chart"></div>' if chart_data else ''}

                    <div class="annual-total">
                        Production totale annuelle :
                        <strong>{simulation.annual_production_kwh:,.2f} kWh</strong>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _generate_css(self):
        """Generate CSS styling per DESIGN SYSTEM v2.0"""

        css = """
        /* PHOTOVOLTAIC REPORT DESIGN SYSTEM v2.0 - PAGE RULES */
        @page {
            size: A4;
            margin: 25mm 20mm 20mm 20mm;

            @top-center {
                content: "VOTRE INSTALLATION PHOTOVOLTAÏQUE";
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 9pt;
                color: #5F6368;
                border-bottom: 1px solid #E0E0E0;
                padding-bottom: 3mm;
            }

            @top-right {
                content: "Page " counter(page) " / " counter(pages);
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 9pt;
                color: #5F6368;
            }

            @bottom-center {
                /* NOTE: Static footer text - WeasyPrint @page boxes cannot use dynamic content
                   TODO: Replace with actual company data: {company.street} | {company.email} | {company.phone} */
                content: "8000 Marina Blvd, Suite 300 | mark.brown23@example.com | Tél: (441)-695-2334";
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 8pt;
                color: #5F6368;
                background: #F5F5F5;
                border-top: 1px solid #E0E0E0;
                padding: 4mm 10mm;
                width: 100%;
            }
        }

        @page :first {
            margin: 0;
            @top-center { content: none; }
            @top-right { content: none; }
            @bottom-center { content: none; }
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
            width: 210mm;
            height: 297mm;
            position: relative;
            page-break-after: always;
        }

        /* ===== COVER PAGE ===== */
        .cover-page {
            background: linear-gradient(135deg, #FAFAFA 0%, #F5F5F5 100%);
            overflow: hidden;
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
            top: 70mm;
            left: 50%;
            transform: translateX(-50%);
            width: 120mm;
            height: 80mm;
        }

        .cover-photo {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 12px;
            border: 3px solid #4A9B5D;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }

        .main-title {
            position: absolute;
            top: 158mm;
            width: 100%;
            text-align: center;
        }

        .title-green {
            color: #4A9B5D;
            font-size: 28pt;
            font-weight: 700;
            margin-bottom: 3mm;
            letter-spacing: 0.5mm;
        }

        .title-black {
            color: #1A1A1A;
            font-size: 28pt;
            font-weight: 700;
            margin-bottom: 6mm;
            letter-spacing: 0.5mm;
        }

        .tagline {
            color: #666;
            font-size: 12pt;
            font-style: italic;
        }

        .customer-box {
            position: absolute;
            top: 208mm;
            left: 25mm;
            right: 25mm;
            background: #FFFFFF;
            padding: 8mm 15mm;
            border-radius: 8px;
            border-left: 4px solid #4A9B5D;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        }

        .customer-box-border {
            display: none;
        }

        .customer-content h3 {
            color: #4A9B5D;
            font-size: 16pt;
            font-weight: 600;
            margin-bottom: 3mm;
            letter-spacing: 0.3mm;
        }

        .customer-name {
            font-size: 13pt;
            font-weight: bold;
            margin-bottom: 1mm;
        }

        .customer-content p {
            margin: 1mm 0;
            font-size: 10pt;
        }

        .customer-contact {
            font-size: 9pt;
        }

        .footer-wave {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 20mm;
            background: #2D7A4F;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 5mm 10mm;
        }

        .footer-content {
            text-align: center;
            color: #FFFFFF;
            string-set: footer-left content();
        }

        .footer-content p {
            margin: 1mm 0;
            font-size: 8pt;
            font-weight: 400;
        }

        /* ===== LOCATION PAGE ===== */
        .location-page {
            background: #F5F5F5;
        }

        .section {
            margin-bottom: 20mm;
            page-break-inside: avoid;
        }

        /* Keep production chart + specs + summary together */
        .production-section {
            page-break-inside: avoid;
        }

        h1 {
            color: #4A9B5D;
            font-size: 28pt;
            font-weight: 700;
            margin-top: 0;
            margin-bottom: 10mm;
            page-break-after: avoid;
        }

        h2 {
            color: #2D7A4F;
            font-size: 20pt;
            font-weight: 600;
            margin-top: 20mm;
            margin-bottom: 10mm;
            page-break-after: avoid;
        }

        h3 {
            color: #4A9B5D;
            font-size: 16pt;
            font-weight: 600;
            margin-bottom: 8mm;
        }

        .section-title {
            color: #2D7A4F;
            font-size: 20pt;
            font-weight: 600;
            margin-top: 15mm;
            margin-bottom: 8mm;
            page-break-after: avoid;
        }

        /* Section underline - gold accent bar */
        .section-underline {
            width: 60px;
            height: 3px;
            background: #F9A825;
            margin-top: 6mm;
            margin-bottom: 12mm;
            border: none;
        }

        .location-info {
            margin-bottom: 10mm;
        }

        .address {
            font-size: 11pt;
            margin-bottom: 5mm;
            color: #1A1A1A;
        }

        p {
            margin-bottom: 8mm;
            color: #1A1A1A;
        }

        strong {
            font-weight: 600;
            color: #2D7A4F;
        }

        .location-image-container {
            text-align: center;
            margin: 12mm auto;
            page-break-inside: avoid;
        }

        .location-image {
            max-width: 170mm;
            height: auto;
            object-fit: cover;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
        }

        /* Info card - specs box with gold accent */
        .production-stats {
            background: #FFFFFF;
            border-left: 4px solid #F9A825;
            border-radius: 0 8px 8px 0;
            padding: 12mm 15mm;
            margin: 10mm 0;
            page-break-inside: avoid;
        }

        .stats-sidebar {
            display: none;
        }

        .stats-content p {
            margin: 4mm 0;
            font-size: 11pt;
            line-height: 1.5;
        }

        .chart-container {
            text-align: center;
            margin: 15mm auto;
            page-break-inside: avoid;
        }

        .chart {
            max-width: 170mm;
            height: auto;
            border-radius: 8px;
        }

        /* Data highlight box - annual production (ATTENTION GRABBER) */
        .annual-total {
            text-align: center;
            font-size: 14pt;
            margin: 15mm auto;
            padding: 15mm 25mm;
            background: #2D7A4F;
            color: #FFFFFF;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            font-weight: 400;
            page-break-inside: avoid;
            max-width: 80%;
        }

        .annual-total strong {
            font-size: 24pt;
            font-weight: 700;
            color: #FFFFFF;
            display: block;
            margin-top: 5mm;
        }

        /* Page footer removed - handled by @page @bottom-center */
        .page-footer {
            display: none;
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
