# -*- coding: utf-8 -*-
"""
PHOTOVOLTAIC REPORT DESIGN SYSTEM v3.0
WeasyPrint-based PDF Report Generator — High-End Dashboard Aesthetic

This module implements a complete redesign of the PV installation report
using Belgogreen brand identity as the foundation.

COLOR PALETTE:
- Primary Eco-Green:  #4CAF50  (brand accent, CTAs, success states)
- Primary Dark:       #388E3C  (emphasis, hover states)
- Primary Light:      #E8F5E9  (tinted backgrounds, spec card fills)
- Deep Charcoal:      #212121  (primary text)
- Secondary Text:     #616161  (metadata, labels)
- Light Grey BG:      #F9F9F9  (section backgrounds)
- Border Grey:        #E0E0E0  (borders, dividers)
- White:              #FFFFFF  (card backgrounds)

TYPOGRAPHY:
- Headings:   'Montserrat', 700 weight
- Body:       'Inter', 400/300 weight
- Hero nums:  'Montserrat', 700 weight, large size

LAYOUT:
- CSS Grid + Flexbox for all layouts
- Page size: A4 (210mm x 297mm)
- WeasyPrint-optimized (no JS, pure CSS)
"""

import io
import base64
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PvSimulationWeasyPrint(models.AbstractModel):
    """WeasyPrint-based PDF Report Generator — Design System v3.0"""
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

        # Generate SVG chart
        chart_svg = ''
        if simulation.monthly_result_ids:
            try:
                chart_svg = self._generate_monthly_chart_svg(simulation)
            except Exception as e:
                _logger.warning(f"Could not generate SVG chart: {e}")

        # Cover title
        raw_cover_title = simulation.cover_title or 'VOTRE INSTALLATION'
        cover_title_line1 = raw_cover_title.replace(' PHOTOVOLTAÏQUE', '').replace('PHOTOVOLTAÏQUE', '').strip()

        # Company data
        company_name = _esc(company.name or '')
        company_email = _esc(company.pv_report_email or company.email or '')
        company_phone = _esc(company.pv_report_phone or company.phone or '')
        company_website = _esc(company.website or '')
        address = _esc(simulation.installation_address or '')

        # Partner info
        partner_name = _esc(partner.name) if partner else ''
        partner_phone = _esc(partner.phone) if partner and partner.phone else ''
        partner_email = _esc(partner.email) if partner and partner.email else ''

        # ---- Bilan Annuel: aggregate monthly results ----
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
            """Format number with 2 decimals and thousand separator, or dash if zero."""
            if not val:
                return '—'
            return f'{val:,.2f}'

        def _is_valid(val):
            """Check if a value is valid (not zero, not None, not dash placeholder)."""
            if val is None:
                return False
            if isinstance(val, (int, float)):
                return val != 0.0
            return str(val).strip() not in ('', '—', '-')

        # Build contact bar for cover footer
        cover_footer_parts = []
        if company_phone:
            cover_footer_parts.append(f"""
                <div class="contact-item">
                    <svg class="contact-icon" viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2">
                        <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
                    </svg>
                    <span>{company_phone}</span>
                </div>""")
        if company_email:
            cover_footer_parts.append(f"""
                <div class="contact-item">
                    <svg class="contact-icon" viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2">
                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                        <polyline points="22,6 12,13 2,6"/>
                    </svg>
                    <span>{company_email}</span>
                </div>""")
        cover_contact_html = '\n'.join(cover_footer_parts)

        # Build Page 2: Site Profile Card
        site_profile_items = []
        if address:
            site_profile_items.append(f"""
                <div class="profile-item">
                    <div class="profile-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" width="24" height="24">
                            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                            <circle cx="12" cy="10" r="3"/>
                        </svg>
                    </div>
                    <div class="profile-detail">
                        <div class="profile-label">Adresse d'installation</div>
                        <div class="profile-value">{address.replace(chr(10), '<br/>')}</div>
                    </div>
                </div>""")
        if simulation.roof_surface_m2:
            site_profile_items.append(f"""
                <div class="profile-item">
                    <div class="profile-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" width="24" height="24">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                            <line x1="3" y1="9" x2="21" y2="9"/>
                            <line x1="9" y1="21" x2="9" y2="9"/>
                        </svg>
                    </div>
                    <div class="profile-detail">
                        <div class="profile-label">Superficie de la toiture</div>
                        <div class="profile-value">{simulation.roof_surface_m2:.0f} m²</div>
                    </div>
                </div>""")
        site_profile_html = '\n'.join(site_profile_items)

        # Build Page 4: Bilan Annuel with conditional rendering
        # Production section
        production_html = ''
        if _is_valid(prod_total):
            production_html = f"""
                <div class="dashboard-card">
                    <div class="card-header">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                            <circle cx="12" cy="12" r="5"/>
                            <line x1="12" y1="1" x2="12" y2="3"/>
                            <line x1="12" y1="21" x2="12" y2="23"/>
                            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                            <line x1="1" y1="12" x2="3" y2="12"/>
                            <line x1="21" y1="12" x2="23" y2="12"/>
                            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                        </svg>
                        <span>Production</span>
                    </div>
                    <div class="card-body card-body-single">
                        <div class="metric-block">
                            <div class="metric-label">Totale</div>
                            <div class="metric-value">{_fmt(prod_total)}</div>
                            <div class="metric-unit">kWh</div>
                        </div>
                    </div>
                </div>"""

        # Consumption section - only render items with values
        conso_items = []
        if _is_valid(conso_day):
            conso_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Jour</div>
                                <div class="metric-value">{_fmt(conso_day)}</div>
                                <div class="metric-unit">kWh</div>
                            </div>""")
        if _is_valid(conso_night):
            conso_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Nuit</div>
                                <div class="metric-value">{_fmt(conso_night)}</div>
                                <div class="metric-unit">kWh</div>
                            </div>""")
        if _is_valid(conso_total):
            conso_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Totale</div>
                                <div class="metric-value">{_fmt(conso_total)}</div>
                                <div class="metric-unit">kWh</div>
                            </div>""")

        consumption_html = ''
        if conso_items:
            consumption_html = f"""
                <div class="dashboard-card">
                    <div class="card-header">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                        </svg>
                        <span>Consommation</span>
                    </div>
                    <div class="card-body">
                        {''.join(conso_items)}
                    </div>
                </div>"""

        # Auto-consumption section
        autocons_items = []
        if _is_valid(autocons_day):
            autocons_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Consommé la journée</div>
                                <div class="metric-value">{_fmt(autocons_day)}</div>
                                <div class="metric-unit">kWh</div>
                            </div>""")
        if _is_valid(battery_charge):
            autocons_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Stocké dans la batterie</div>
                                <div class="metric-value">{_fmt(battery_charge)}</div>
                                <div class="metric-unit">kWh</div>
                            </div>""")
        if _is_valid(autocons_total):
            autocons_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Total</div>
                                <div class="metric-value">{_fmt(autocons_total)}</div>
                                <div class="metric-unit">kWh</div>
                            </div>""")

        autocons_html = ''
        if autocons_items:
            autocons_html = f"""
                <div class="dashboard-card dashboard-card-full">
                    <div class="card-header">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                        </svg>
                        <span>Auto Consommation</span>
                    </div>
                    <div class="card-body">
                        {''.join(autocons_items)}
                    </div>
                </div>"""

        # Economies section - only render items with values
        econ_items = []
        if _is_valid(savings_panels):
            econ_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Liées aux panneaux</div>
                                <div class="metric-value">{_fmt(savings_panels)}</div>
                                <div class="metric-unit">&euro;</div>
                            </div>""")
        if _is_valid(savings_battery):
            econ_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Liées à la batterie</div>
                                <div class="metric-value">{_fmt(savings_battery)}</div>
                                <div class="metric-unit">&euro;</div>
                            </div>""")
        if _is_valid(savings_resale):
            econ_items.append(f"""
                            <div class="metric-block">
                                <div class="metric-label">Liées à la revente</div>
                                <div class="metric-value">{_fmt(savings_resale)}</div>
                                <div class="metric-unit">&euro;</div>
                            </div>""")

        economies_html = ''
        if econ_items:
            economies_html = f"""
                <div class="dashboard-card dashboard-card-full">
                    <div class="card-header">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                            <line x1="12" y1="1" x2="12" y2="23"/>
                            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                        </svg>
                        <span>Economies</span>
                    </div>
                    <div class="card-body">
                        {''.join(econ_items)}
                    </div>
                </div>"""

        # Bottom summary row
        bottom_row_parts = []
        if _is_valid(savings_total):
            bottom_row_parts.append(f"""
                    <div class="summary-box summary-success">
                        <div class="summary-label">Total économies</div>
                        <div class="summary-value">{_fmt(savings_total)} &euro;</div>
                    </div>""")
        if _is_valid(purchase_total):
            bottom_row_parts.append(f"""
                    <div class="summary-box summary-purchase">
                        <div class="summary-label">Achat</div>
                        <div class="summary-value">{_fmt(purchase_total)} &euro;</div>
                    </div>""")
        bottom_row_html = '\n'.join(bottom_row_parts)

        # Streamlined footer text
        footer_parts = [company_name]
        if company_website:
            footer_parts.append(company_website)
        footer_text = ' &nbsp;|&nbsp; '.join(filter(None, footer_parts))

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Installation Photovoltaïque — {company_name}</title>
</head>
<body>
    <!-- Running footer element (picked up by CSS @page) -->
    <div class="running-footer">
        <span class="footer-brand">{footer_text}</span>
    </div>

    <!-- ==================== PAGE 1: COVER ==================== -->
    <div class="page cover-page">
        <!-- Full-width hero image -->
        <div class="hero-image-container">
            {f'<img src="{cover_photo_data}" alt="" class="hero-image">' if cover_photo_data else '<div class="hero-placeholder"></div>'}
            <div class="hero-overlay"></div>
        </div>

        <!-- Logo positioned prominently -->
        <div class="cover-logo">
            {f'<img src="{logo_data}" alt="{company_name}" class="cover-logo-img">' if logo_data else ''}
        </div>

        <!-- Title block -->
        <div class="cover-title-block">
            <h1 class="cover-title">{_esc(cover_title_line1)}</h1>
            <h1 class="cover-title cover-title-accent">PHOTOVOLTAÏQUE</h1>
            <p class="cover-tagline">{_esc(company.pv_report_tagline or 'Save your planet. Save your wallet.')}</p>
        </div>

        <!-- Client info card -->
        <div class="cover-client-card">
            {f'<div class="client-name">{partner_name}</div>' if partner_name else ''}
            {f'<div class="client-detail">{partner_phone}</div>' if partner_phone else ''}
            {f'<div class="client-detail">{partner_email}</div>' if partner_email else ''}
        </div>

        <!-- Bottom contact bar -->
        <div class="cover-contact-bar">
            <div class="contact-bar-inner">
                {cover_contact_html}
            </div>
        </div>
    </div>

    <!-- ==================== PAGE 2: SITE LOCALIZATION ==================== -->
    <div class="page content-page">
        <h2 class="section-heading">{_esc(simulation.section_title_location or "LOCALISATION DE L'INSTALLATION")}</h2>
        <div class="heading-rule"></div>

        <!-- Site Profile Card -->
        <div class="site-profile-card">
            <div class="profile-grid">
                {site_profile_html}
            </div>
        </div>

        <!-- Satellite / Location Image -->
        {f'''<div class="map-container">
            <img src="{location_image_data}" alt="Localisation" class="map-image">
        </div>''' if location_image_data else ''}
    </div>

    <!-- ==================== PAGE 3: PRODUCTION ANALYSIS ==================== -->
    <div class="page content-page">
        <h2 class="section-heading">{_esc(simulation.section_title_production or 'ANALYSE DE PRODUCTION')}</h2>
        <div class="heading-rule"></div>

        <!-- Technical Spec Cards -->
        <div class="spec-cards">
            <div class="spec-card">
                <div class="spec-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" width="28" height="28">
                        <rect x="2" y="7" width="20" height="15" rx="2" ry="2"/>
                        <polyline points="17 2 12 7 7 2"/>
                    </svg>
                </div>
                <div class="spec-value">{simulation.total_pv_power_wc:,.0f}</div>
                <div class="spec-unit">Wc</div>
                <div class="spec-label">Puissance</div>
            </div>
            {f'''<div class="spec-card">
                <div class="spec-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" width="28" height="28">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="2" y1="12" x2="22" y2="12"/>
                        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                    </svg>
                </div>
                <div class="spec-value">{simulation.orientation_deg:.0f}°</div>
                <div class="spec-unit">&nbsp;</div>
                <div class="spec-label">Orientation</div>
            </div>''' if simulation.orientation_deg else ''}
            {f'''<div class="spec-card">
                <div class="spec-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" width="28" height="28">
                        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
                        <polyline points="17 6 23 6 23 12"/>
                    </svg>
                </div>
                <div class="spec-value">{simulation.tilt_deg:.0f}°</div>
                <div class="spec-unit">&nbsp;</div>
                <div class="spec-label">Inclinaison</div>
            </div>''' if simulation.tilt_deg else ''}
        </div>

        <!-- Monthly Production SVG Chart -->
        {f'<div class="chart-wrapper">{chart_svg}</div>' if chart_svg else ''}

        <!-- Annual Total Highlight -->
        <div class="annual-total-box">
            <div class="annual-total-label">Production totale annuelle</div>
            <div class="annual-total-value">{simulation.annual_production_kwh:,.2f} kWh</div>
        </div>
    </div>

    <!-- ==================== PAGE 4: ANNUAL BALANCE DASHBOARD ==================== -->
    <div class="page content-page">
        <h2 class="section-heading">BILAN ANNUEL</h2>
        <div class="heading-rule"></div>

        <div class="dashboard-grid">
            <!-- Top row: Production + Consumption -->
            <div class="dashboard-top-row">
                {production_html}
                {consumption_html}
            </div>

            <!-- Auto-consumption -->
            {autocons_html}

            <!-- Economies -->
            {economies_html}

            <!-- Summary row -->
            <div class="summary-row">
                {bottom_row_html}
            </div>
        </div>
    </div>
</body>
</html>"""

        return html

    def _generate_css(self):
        """Generate CSS styling — Design System v3.0"""

        css = """
        /* ==========================================================
           PHOTOVOLTAIC REPORT — DESIGN SYSTEM v3.0
           High-End Dashboard Aesthetic · Belgogreen Brand Identity
           ========================================================== */

        /* ---------- RUNNING FOOTER (content pages) ---------- */
        .running-footer {
            position: running(pageFooter);
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            font-size: 8pt;
            color: #9E9E9E;
            text-align: center;
            padding: 2mm 0 0 0;
        }

        .footer-brand {
            letter-spacing: 0.3mm;
        }

        /* ---------- PAGE RULES ---------- */
        @page {
            size: A4;
            margin: 18mm 20mm 22mm 20mm;

            @bottom-center {
                content: element(pageFooter);
                border-top: 1px solid #E0E0E0;
                padding-top: 3mm;
                width: 100%;
                vertical-align: top;
            }

            @bottom-right {
                content: "Page " counter(page) " / " counter(pages);
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 7.5pt;
                color: #9E9E9E;
                border-top: 1px solid #E0E0E0;
                padding-top: 3mm;
                vertical-align: top;
            }
        }

        @page :first {
            margin: 0;
            @bottom-center { content: none; }
            @bottom-right { content: none; }
        }

        /* ---------- RESET & BASE ---------- */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 10.5pt;
            color: #212121;
            line-height: 1.55;
            font-weight: 400;
        }

        .page {
            page-break-after: always;
        }

        /* ==========================================================
           PAGE 1 — PROFESSIONAL COVER
           ========================================================== */
        .cover-page {
            width: 210mm;
            height: 297mm;
            position: relative;
            background: #FFFFFF;
            overflow: hidden;
        }

        /* Hero image — full-width, top section */
        .hero-image-container {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 55%;
            overflow: hidden;
        }

        .hero-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }

        .hero-placeholder {
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 50%, #A5D6A7 100%);
        }

        .hero-overlay {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 40%;
            background: linear-gradient(to top, #FFFFFF 0%, rgba(255,255,255,0.85) 40%, rgba(255,255,255,0) 100%);
        }

        /* Logo */
        .cover-logo {
            position: absolute;
            top: 18mm;
            left: 20mm;
            z-index: 10;
        }

        .cover-logo-img {
            max-height: 16mm;
            max-width: 50mm;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.15));
        }

        /* Title block — positioned over the fade */
        .cover-title-block {
            position: absolute;
            top: 52%;
            left: 0;
            width: 100%;
            text-align: center;
            padding: 0 25mm;
        }

        .cover-title {
            font-family: 'Montserrat', 'Inter', 'Segoe UI', sans-serif;
            font-size: 30pt;
            font-weight: 700;
            color: #212121;
            letter-spacing: 1mm;
            line-height: 1.2;
            margin: 0;
        }

        .cover-title-accent {
            color: #4CAF50;
            margin-top: 2mm;
        }

        .cover-tagline {
            font-size: 11pt;
            font-weight: 300;
            color: #616161;
            font-style: italic;
            margin-top: 6mm;
            letter-spacing: 0.3mm;
        }

        /* Client info card */
        .cover-client-card {
            position: absolute;
            bottom: 50mm;
            left: 25mm;
            right: 25mm;
            background: #F9F9F9;
            border-left: 4px solid #4CAF50;
            border-radius: 0 8px 8px 0;
            padding: 8mm 12mm;
        }

        .client-name {
            font-family: 'Montserrat', 'Inter', sans-serif;
            font-size: 14pt;
            font-weight: 700;
            color: #212121;
            margin-bottom: 2mm;
        }

        .client-detail {
            font-size: 10pt;
            color: #616161;
            line-height: 1.6;
        }

        /* Contact bar footer */
        .cover-contact-bar {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: #FAFAFA;
            border-top: 1px solid #E0E0E0;
            padding: 5mm 25mm;
        }

        .contact-bar-inner {
            display: flex;
            justify-content: center;
            gap: 12mm;
        }

        .contact-item {
            display: flex;
            align-items: center;
            gap: 2mm;
            font-size: 9pt;
            color: #616161;
        }

        .contact-icon {
            width: 14px;
            height: 14px;
            flex-shrink: 0;
        }

        /* ==========================================================
           CONTENT PAGES — SHARED STYLES
           ========================================================== */
        .content-page {
            padding: 0;
        }

        .section-heading {
            font-family: 'Montserrat', 'Inter', 'Segoe UI', sans-serif;
            font-size: 18pt;
            font-weight: 700;
            color: #212121;
            letter-spacing: 0.5mm;
            margin: 0 0 3mm 0;
            page-break-after: avoid;
        }

        .heading-rule {
            width: 50px;
            height: 3px;
            background: #4CAF50;
            margin-bottom: 10mm;
            border-radius: 2px;
        }

        /* ==========================================================
           PAGE 2 — SITE LOCALIZATION
           ========================================================== */

        /* Site Profile Card */
        .site-profile-card {
            background: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 12px;
            padding: 8mm;
            margin-bottom: 10mm;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }

        .profile-grid {
            display: flex;
            gap: 8mm;
        }

        .profile-item {
            flex: 1;
            display: flex;
            align-items: flex-start;
            gap: 4mm;
        }

        .profile-icon {
            flex-shrink: 0;
            width: 36px;
            height: 36px;
            background: #E8F5E9;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 6px;
        }

        .profile-label {
            font-size: 8pt;
            color: #9E9E9E;
            text-transform: uppercase;
            letter-spacing: 0.3mm;
            margin-bottom: 1mm;
            font-weight: 600;
        }

        .profile-value {
            font-size: 11pt;
            color: #212121;
            font-weight: 500;
            line-height: 1.4;
        }

        /* Map container with rounded frame and shadow */
        .map-container {
            text-align: center;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 16px rgba(0,0,0,0.08);
            border: 1px solid #E0E0E0;
            margin: 0 auto;
            max-width: 160mm;
        }

        .map-image {
            width: 100%;
            max-height: 130mm;
            object-fit: cover;
            display: block;
        }

        /* ==========================================================
           PAGE 3 — PRODUCTION ANALYSIS
           ========================================================== */

        /* Spec Cards row */
        .spec-cards {
            display: flex;
            gap: 5mm;
            margin-bottom: 10mm;
        }

        .spec-card {
            flex: 1;
            background: #F1F8E9;
            border: 1px solid #C5E1A5;
            border-radius: 10px;
            padding: 6mm 4mm;
            text-align: center;
            page-break-inside: avoid;
        }

        .spec-icon {
            margin-bottom: 3mm;
        }

        .spec-value {
            font-family: 'Montserrat', 'Inter', sans-serif;
            font-size: 22pt;
            font-weight: 700;
            color: #212121;
            line-height: 1.1;
        }

        .spec-unit {
            font-size: 10pt;
            font-weight: 600;
            color: #4CAF50;
            margin-bottom: 1mm;
        }

        .spec-label {
            font-size: 8.5pt;
            color: #616161;
            text-transform: uppercase;
            letter-spacing: 0.3mm;
            font-weight: 600;
        }

        /* Chart wrapper */
        .chart-wrapper {
            margin: 6mm 0 8mm 0;
            page-break-inside: avoid;
        }

        .chart-wrapper svg {
            width: 100%;
            height: auto;
        }

        /* Annual total highlight box */
        .annual-total-box {
            background: #212121;
            color: #FFFFFF;
            border-radius: 10px;
            padding: 6mm 10mm;
            display: flex;
            align-items: center;
            justify-content: space-between;
            page-break-inside: avoid;
        }

        .annual-total-label {
            font-size: 12pt;
            font-weight: 600;
            letter-spacing: 0.3mm;
        }

        .annual-total-value {
            font-family: 'Montserrat', 'Inter', sans-serif;
            font-size: 20pt;
            font-weight: 700;
            color: #4CAF50;
        }

        /* ==========================================================
           PAGE 4 — ANNUAL BALANCE DASHBOARD
           ========================================================== */
        .dashboard-grid {
            page-break-inside: avoid;
        }

        .dashboard-top-row {
            display: flex;
            gap: 4mm;
            margin-bottom: 4mm;
        }

        .dashboard-card {
            flex: 1;
            background: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 4mm;
        }

        .dashboard-card-full {
            width: 100%;
        }

        .card-header {
            background: #4CAF50;
            color: #FFFFFF;
            padding: 3mm 5mm;
            display: flex;
            align-items: center;
            gap: 2mm;
            font-family: 'Montserrat', 'Inter', sans-serif;
            font-size: 10pt;
            font-weight: 600;
            letter-spacing: 0.3mm;
        }

        .card-header svg {
            flex-shrink: 0;
        }

        .card-body {
            display: flex;
            justify-content: space-around;
            padding: 5mm 4mm;
            gap: 2mm;
        }

        .card-body-single {
            justify-content: center;
        }

        .metric-block {
            text-align: center;
            flex: 1;
            padding: 2mm;
        }

        .metric-label {
            font-size: 7.5pt;
            color: #9E9E9E;
            text-transform: uppercase;
            letter-spacing: 0.2mm;
            margin-bottom: 1.5mm;
            font-weight: 600;
        }

        .metric-value {
            font-family: 'Montserrat', 'Inter', sans-serif;
            font-size: 12pt;
            font-weight: 700;
            color: #212121;
            line-height: 1.2;
        }

        .metric-unit {
            font-size: 8pt;
            color: #616161;
            margin-top: 0.5mm;
        }

        /* Summary row */
        .summary-row {
            display: flex;
            gap: 4mm;
            margin-top: 4mm;
        }

        .summary-box {
            flex: 1;
            border-radius: 10px;
            padding: 5mm 8mm;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* SUCCESS BOX: solid green bg, white text — emphasizes ROI */
        .summary-success {
            background: #4CAF50;
            color: #FFFFFF;
        }

        .summary-success .summary-label {
            color: rgba(255,255,255,0.9);
        }

        .summary-success .summary-value {
            color: #FFFFFF;
            font-family: 'Montserrat', 'Inter', sans-serif;
            font-size: 14pt;
            font-weight: 700;
        }

        .summary-purchase {
            background: #F9F9F9;
            border: 1px solid #E0E0E0;
            color: #212121;
        }

        .summary-label {
            font-size: 10pt;
            font-weight: 600;
        }

        .summary-value {
            font-family: 'Montserrat', 'Inter', sans-serif;
            font-size: 14pt;
            font-weight: 700;
        }

        .summary-purchase .summary-value {
            color: #212121;
        }
        """

        return css

    def _generate_monthly_chart_svg(self, simulation):
        """
        Generate a clean SVG bar chart for monthly production.
        Returns raw SVG markup string for direct embedding in HTML.
        Uses gradient-filled bars; no repeated 'kWh' labels on Y-axis.
        """
        monthly_results = simulation.monthly_result_ids.sorted(key=lambda r: int(r.month))
        if not monthly_results:
            return ''

        # Get data
        month_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
                        'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
        values = []
        for r in monthly_results:
            val = r.production_pv_kwh if hasattr(r, 'production_pv_kwh') and r.production_pv_kwh else r.daily_production_kwh
            values.append(val)

        if not values or max(values) == 0:
            return ''

        max_val = max(values)

        # SVG dimensions
        svg_w = 700
        svg_h = 280
        margin_left = 40
        margin_right = 20
        margin_top = 25
        margin_bottom = 40
        chart_w = svg_w - margin_left - margin_right
        chart_h = svg_h - margin_top - margin_bottom
        bar_count = len(values)
        bar_gap = 8
        bar_width = (chart_w - (bar_count - 1) * bar_gap) / bar_count

        # Calculate nice Y-axis ticks
        y_step = max_val / 4
        # Round to nice numbers
        if y_step > 100:
            y_step = round(y_step / 50) * 50
        elif y_step > 10:
            y_step = round(y_step / 5) * 5
        else:
            y_step = round(y_step, 1)
        if y_step == 0:
            y_step = 1

        # Build SVG
        svg_parts = []
        svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" '
                         f'style="width:100%; height:auto; font-family: Inter, Segoe UI, Arial, sans-serif;">')

        # Gradient definition
        svg_parts.append('''
        <defs>
            <linearGradient id="barGrad" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stop-color="#81C784"/>
                <stop offset="100%" stop-color="#388E3C"/>
            </linearGradient>
        </defs>''')

        # Background
        svg_parts.append(f'<rect x="0" y="0" width="{svg_w}" height="{svg_h}" fill="#FFFFFF" rx="8"/>')

        # Y-axis grid lines (no 'kWh' repeated)
        y_val = 0
        while y_val <= max_val * 1.15:
            y_pos = margin_top + chart_h - (y_val / (max_val * 1.15)) * chart_h
            svg_parts.append(
                f'<line x1="{margin_left}" y1="{y_pos:.1f}" x2="{svg_w - margin_right}" y2="{y_pos:.1f}" '
                f'stroke="#EEEEEE" stroke-width="1"/>')
            label = f'{y_val:.0f}' if y_val == int(y_val) else f'{y_val:.1f}'
            svg_parts.append(
                f'<text x="{margin_left - 4}" y="{y_pos + 3:.1f}" text-anchor="end" '
                f'fill="#9E9E9E" font-size="9">{label}</text>')
            y_val += y_step

        # Single 'kWh' label at top of Y-axis
        svg_parts.append(
            f'<text x="{margin_left - 4}" y="{margin_top - 8}" text-anchor="end" '
            f'fill="#9E9E9E" font-size="8" font-weight="600">kWh</text>')

        # Bars with gradient
        for i, (val, label) in enumerate(zip(values, month_labels)):
            x = margin_left + i * (bar_width + bar_gap)
            bar_h = (val / (max_val * 1.15)) * chart_h if max_val > 0 else 0
            y = margin_top + chart_h - bar_h

            # Bar with rounded top
            svg_parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_h:.1f}" '
                f'fill="url(#barGrad)" rx="3" ry="3"/>')

            # Value label on top
            svg_parts.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" '
                f'fill="#212121" font-size="9" font-weight="600">{val:.1f}</text>')

            # Month label below
            svg_parts.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{margin_top + chart_h + 15:.1f}" text-anchor="middle" '
                f'fill="#616161" font-size="9" font-weight="500">{label}</text>')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def _generate_monthly_chart(self, simulation):
        """Generate monthly production bar chart using matplotlib (fallback)"""
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
            monthly_results = simulation.monthly_result_ids.sorted(key=lambda r: r.month)
            if not monthly_results:
                return None

            months = [r.month for r in monthly_results]
            production = [r.production_pv_kwh for r in monthly_results]

            month_labels = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

            fig, ax = plt.subplots(figsize=(10, 4))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('#FFFFFF')

            bars = ax.bar(range(len(months)), production,
                         color='#4CAF50',
                         edgecolor='#388E3C',
                         linewidth=1.2,
                         width=0.75)

            for bar, val in zip(bars, production):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{val:.1f}',
                       ha='center', va='bottom', fontsize=9,
                       fontweight='600', color='#212121')

            ax.set_xticks(range(len(months)))
            ax.set_xticklabels(month_labels, fontsize=10, fontweight='500', color='#616161')
            ax.set_ylabel('kWh', fontsize=11, fontweight='600', color='#616161')

            ax.grid(axis='y', alpha=1.0, linestyle='-', linewidth=0.5, color='#EEEEEE')
            ax.set_axisbelow(True)

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#E0E0E0')
            ax.spines['bottom'].set_linewidth(0.5)
            ax.spines['left'].set_color('#E0E0E0')
            ax.spines['left'].set_linewidth(0.5)

            ax.tick_params(axis='both', which='both', length=0, labelcolor='#616161', labelsize=10)

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
