# -*- coding: utf-8 -*-

import io
import base64
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PvSimulationReportLab(models.AbstractModel):
    """ReportLab-based PDF Report Generator"""
    _name = 'pv.simulation.reportlab.generator'
    _description = 'ReportLab Report Generator for PV Simulation'

    @api.model
    def generate_report(self, simulation_id):
        """
        Generate a professional PDF report using ReportLab

        Args:
            simulation_id: pv.simulation record ID

        Returns:
            bytes: PDF file content
        """
        # Import ReportLab
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import mm, cm
            from reportlab.lib.colors import HexColor
            from reportlab.lib.utils import ImageReader
        except ImportError as e:
            _logger.error(f"ReportLab not installed: {e}")
            raise Exception(
                "ReportLab is required for this report.\n\n"
                "Installation:\n"
                "  pip install reportlab\n\n"
                "If you're on Odoo.sh or cloud environment, add 'reportlab>=4.0.0' to requirements.txt"
            )

        # Try to import matplotlib (optional - for charts)
        matplotlib_available = False
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            matplotlib_available = True
            _logger.info("Matplotlib available - charts will be generated")
        except ImportError as e:
            _logger.warning(f"Matplotlib not available: {e}. Charts will be skipped.")
            matplotlib_available = False
        except Exception as e:
            _logger.warning(f"Matplotlib import error: {e}. Charts will be skipped.")
            matplotlib_available = False

        simulation = self.env['pv.simulation'].browse(simulation_id)

        # Create PDF in memory
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4  # 210mm x 297mm

        # Brand colors
        green_primary = HexColor('#8BC34A')
        green_dark = HexColor('#7CB342')
        black = HexColor('#000000')
        white = HexColor('#FFFFFF')
        gray_light = HexColor('#F5F5F5')

        # ========================================
        # PAGE 1: COVER PAGE
        # ========================================
        _logger.info("Generating Page 1: Cover Page")

        # Logo (top right)
        if simulation.company_id.pv_report_logo:
            try:
                logo_data = base64.b64decode(simulation.company_id.pv_report_logo)
                logo_img = ImageReader(io.BytesIO(logo_data))
                c.drawImage(logo_img, width - 100*mm, height - 50*mm,
                           width=40*mm, height=40*mm, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                _logger.warning(f"Could not load logo: {e}")

        # Organic blob shapes (decorative background)
        # Simplified as circles for demo - you can use SVG paths for real blobs
        c.setFillColor(HexColor('#E8F5E9'))  # Very light green
        c.setStrokeColor(HexColor('#E8F5E9'))
        c.circle(100*mm, height - 120*mm, 80*mm, fill=1, stroke=0)
        c.circle(150*mm, height - 100*mm, 60*mm, fill=1, stroke=0)

        # Cover Photo (circular with border)
        if simulation.cover_photo:
            try:
                photo_data = base64.b64decode(simulation.cover_photo)
                photo_img = ImageReader(io.BytesIO(photo_data))

                # Draw circular photo at center
                photo_x = width / 2
                photo_y = height - 140*mm
                photo_radius = 60*mm

                # Green border circle
                c.setFillColor(green_primary)
                c.circle(photo_x, photo_y, photo_radius + 2*mm, fill=1, stroke=0)

                # Photo (using clipping for circular shape)
                # Note: ReportLab doesn't support circular clipping directly
                # For now, we'll use a square image - in production, pre-process to circular
                c.drawImage(photo_img, photo_x - photo_radius, photo_y - photo_radius,
                           width=photo_radius * 2, height=photo_radius * 2,
                           preserveAspectRatio=True, mask='auto')
            except Exception as e:
                _logger.warning(f"Could not load cover photo: {e}")

        # Main Title
        c.setFillColor(green_primary)
        c.setFont("Helvetica-Bold", 36)
        title_text = simulation.cover_title or "VOTRE INSTALLATION"
        c.drawCentredString(width / 2, height - 240*mm, title_text)

        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 36)
        c.drawCentredString(width / 2, height - 250*mm, "PHOTOVOLTAÏQUE")

        # Tagline
        c.setFillColor(HexColor('#666666'))
        c.setFont("Helvetica-Oblique", 14)
        tagline = simulation.company_id.pv_report_tagline or "Save your planet. Save your wallet."
        c.drawCentredString(width / 2, height - 260*mm, tagline)

        # Customer Info Box
        box_y = height - 290*mm
        box_height = 40*mm

        # Background box
        c.setFillColor(gray_light)
        c.rect(20*mm, box_y - box_height, width - 40*mm, box_height, fill=1, stroke=0)

        # Green left border
        c.setFillColor(green_primary)
        c.rect(20*mm, box_y - box_height, 4*mm, box_height, fill=1, stroke=0)

        # Customer info text
        c.setFillColor(green_primary)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(28*mm, box_y - 10*mm, "CLIENT")

        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 12)
        if simulation.sale_order_id and simulation.sale_order_id.partner_id:
            partner = simulation.sale_order_id.partner_id
            c.drawString(28*mm, box_y - 18*mm, partner.name or "")

            c.setFont("Helvetica", 10)
            if partner.phone:
                c.drawString(28*mm, box_y - 24*mm, f"Tél: {partner.phone}")
            if partner.email:
                c.drawString(28*mm, box_y - 29*mm, f"Email: {partner.email}")
            if simulation.installation_address:
                c.drawString(28*mm, box_y - 34*mm, f"Adresse: {simulation.installation_address}")

        # Footer wave and contact bar
        # Simplified as rectangle - you can use bezier curves for real waves
        c.setFillColor(green_primary)
        c.rect(0, 0, width, 40*mm, fill=1, stroke=0)

        # Footer contact info (white text on green)
        c.setFillColor(white)
        c.setFont("Helvetica", 9)

        footer_y = 25*mm
        # Company address
        if simulation.company_id.street:
            c.drawCentredString(width / 2, footer_y,
                f"{simulation.company_id.street} - {simulation.company_id.zip} {simulation.company_id.city}")

        footer_y -= 5*mm
        # Salesperson contact (name, phone, email)
        if simulation.sale_order_id and simulation.sale_order_id.user_id:
            user = simulation.sale_order_id.user_id
            phone = user.phone or simulation.company_id.phone
            email = user.email or user.login or ''
            c.drawCentredString(width / 2, footer_y,
                f"{user.name} | Tél: {phone} | {email}")

        footer_y -= 5*mm
        if simulation.company_id.vat:
            c.drawCentredString(width / 2, footer_y, f"TVA: {simulation.company_id.vat}")

        # ========================================
        # PAGE 2: LOCATION & PRODUCTION
        # ========================================
        c.showPage()  # New page
        _logger.info("Generating Page 2: Location & Production")

        # Section Header
        c.setFillColor(green_primary)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(20*mm, height - 30*mm, "LOCALISATION DE L'INSTALLATION")

        # Underline
        c.setLineWidth(3)
        c.setStrokeColor(green_primary)
        c.line(20*mm, height - 32*mm, width - 20*mm, height - 32*mm)

        # Installation address
        c.setFillColor(black)
        c.setFont("Helvetica", 12)
        y_pos = height - 45*mm

        if simulation.installation_address:
            c.drawString(20*mm, y_pos, simulation.installation_address)
            y_pos -= 7*mm

        if simulation.roof_surface_m2:
            c.drawString(20*mm, y_pos, f"Superficie de la toiture : {simulation.roof_surface_m2:.0f} m²")
            y_pos -= 10*mm

        # Location Image (Google Solar API imagery)
        if simulation.location_image:
            try:
                img_data = base64.b64decode(simulation.location_image)
                img = ImageReader(io.BytesIO(img_data))

                # Draw with rounded corner effect (simplified)
                img_width = 120*mm
                img_height = 70*mm
                img_x = (width - img_width) / 2
                img_y = y_pos - img_height

                # Green border
                c.setFillColor(green_primary)
                c.setStrokeColor(green_primary)
                c.setLineWidth(2)
                c.roundRect(img_x - 2*mm, img_y - 2*mm,
                           img_width + 4*mm, img_height + 4*mm,
                           5*mm, fill=0, stroke=1)

                # Image
                c.drawImage(img, img_x, img_y,
                           width=img_width, height=img_height,
                           preserveAspectRatio=True, mask='auto')

                y_pos = img_y - 15*mm
            except Exception as e:
                _logger.warning(f"Could not load location image: {e}")

        # Production Section Header
        c.setFillColor(green_primary)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(20*mm, y_pos, "PRODUCTION MOYENNE JOURNALIÈRE")

        c.setLineWidth(3)
        c.setStrokeColor(green_primary)
        c.line(20*mm, y_pos - 2*mm, width - 20*mm, y_pos - 2*mm)

        y_pos -= 12*mm

        # Production stats with yellow sidebar
        c.setFillColor(HexColor('#FFC107'))  # Yellow accent
        c.rect(20*mm, y_pos - 25*mm, 3*mm, 25*mm, fill=1, stroke=0)

        c.setFillColor(black)
        c.setFont("Helvetica", 11)
        stats_x = 25*mm
        c.drawString(stats_x, y_pos, f"Puissance panneaux : {simulation.total_pv_power_wc:.0f} Wc")
        y_pos -= 6*mm

        if simulation.orientation_deg:
            c.drawString(stats_x, y_pos, f"Orientation : {simulation.orientation_deg:.0f}°")
            y_pos -= 6*mm

        if simulation.tilt_deg:
            c.drawString(stats_x, y_pos, f"Inclinaison : {simulation.tilt_deg:.0f}°")
            y_pos -= 15*mm

        # Generate Monthly Production Chart
        if simulation.monthly_result_ids and matplotlib_available:
            try:
                chart_buffer = self._generate_monthly_chart(simulation)
                if chart_buffer:
                    chart_img = ImageReader(chart_buffer)
                    chart_width = width - 40*mm
                    chart_height = 80*mm
                    c.drawImage(chart_img, 20*mm, y_pos - chart_height,
                               width=chart_width, height=chart_height,
                               preserveAspectRatio=True)
                    y_pos -= chart_height + 10*mm
            except Exception as e:
                _logger.warning(f"Could not generate chart: {e}")
        elif simulation.monthly_result_ids and not matplotlib_available:
            # Add a text note that chart is not available
            c.setFillColor(HexColor('#666666'))
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(20*mm, y_pos - 20*mm, "[Chart not available - matplotlib not installed]")
            y_pos -= 30*mm

        # Annual Production Total
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2, y_pos,
            f"Production totale annuelle : {simulation.annual_production_kwh:,.2f} kWh")

        # Footer on page 2
        c.setFillColor(green_primary)
        c.setFont("Helvetica", 8)
        footer_y = 15*mm

        # Salesperson contact info
        if simulation.sale_order_id and simulation.sale_order_id.user_id:
            user = simulation.sale_order_id.user_id
            phone = user.phone or simulation.company_id.phone
            email = user.email or user.login or ''
            footer_text = f"{simulation.company_id.street} | {email} | Tél: {phone}"
        else:
            footer_text = f"{simulation.company_id.street} | {simulation.company_id.email or ''} | {simulation.company_id.phone or ''}"

        c.drawCentredString(width / 2, footer_y, footer_text)

        # Save PDF
        c.save()

        _logger.info("ReportLab PDF generated successfully")
        return buffer.getvalue()

    def _generate_monthly_chart(self, simulation):
        """Generate monthly production bar chart using matplotlib"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')

            # Get monthly data
            monthly_results = simulation.monthly_result_ids.sorted(key=lambda r: r.month)

            if not monthly_results:
                return None

            months = [r.month for r in monthly_results]
            production = [r.production_pv_kwh for r in monthly_results]

            # Month labels (French)
            month_labels = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

            # Create figure
            fig, ax = plt.subplots(figsize=(10, 4))

            bars = ax.bar(range(len(months)), production, color='#8BC34A', edgecolor='#7CB342', linewidth=1.5)

            # Add value labels on bars
            for i, (bar, val) in enumerate(zip(bars, production)):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{val:.1f}',
                       ha='center', va='bottom', fontsize=9, fontweight='bold')

            # Styling
            ax.set_xticks(range(len(months)))
            ax.set_xticklabels(month_labels)
            ax.set_ylabel('kWh', fontsize=10)
            ax.grid(axis='y', alpha=0.3, linestyle='--')

            # Remove ALL borders/spines for clean look
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.spines['left'].set_visible(False)

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
