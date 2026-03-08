# -*- coding: utf-8 -*-

import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class PvSimulation(models.Model):
    _name = 'pv.simulation'
    _description = 'PV Simulation'
    _order = 'create_date desc'

    # Core Fields
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Quotation',
        required=True,
        ondelete='restrict'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    installation_address = fields.Text(
        string='Installation Address',
        compute='_compute_installation_address',
        help='Installation address (from customer address, read-only)'
    )
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7)
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7)
    )
    location_image = fields.Binary(
        string='Location Image',
        help='Satellite or map image of installation location'
    )
    location_image_filename = fields.Char(
        string='Image Filename'
    )
    report_date = fields.Date(
        string='Report Date',
        default=fields.Date.today
    )

    # Cover Page Customization
    cover_photo = fields.Binary(
        string='Cover Photo',
        help='Cover page photo (configurable per quotation)'
    )
    cover_photo_filename = fields.Char(
        string='Cover Photo Filename'
    )
    cover_title = fields.Char(
        string='Cover Title',
        default='VOTRE INSTALLATION PHOTOVOLTAÏQUE',
        help='Main title on cover page'
    )

    # Section Titles (Configurable per Quotation)
    section_title_location = fields.Char(
        string='Location Section Title',
        default='LOCALISATION DE L\'INSTALLATION',
        help='Page 2: Installation location section'
    )
    section_title_production = fields.Char(
        string='Production Section Title',
        default='PRODUCTION MOYENNE JOURNALIÈRE',
        help='Page 2: Production section'
    )

    # PV System Parameters
    roof_surface_m2 = fields.Float(
        string='Roof Surface (m²)',
        help='Available roof surface in square meters'
    )
    number_of_panels = fields.Integer(
        string='Number of Panels',
        compute='_compute_panel_data',
        store=True,
        help='Total number of solar panels (from sale order line items)'
    )
    max_panels_count = fields.Integer(
        string='Max Panels (Roof Capacity)',
        help='Maximum number of panels the roof can accommodate (from Google Solar API)'
    )
    panel_unit_power_wc = fields.Float(
        string='Panel Unit Power (Wc)',
        compute='_compute_panel_data',
        store=True,
        help='Power per panel in Wc (from product specification)'
    )
    total_pv_power_wc = fields.Float(
        string='Total PV Power (Wc)',
        compute='_compute_panel_data',
        store=True,
        help='Installed PV power in Wc (calculated: number of panels × unit power)'
    )
    orientation_deg = fields.Float(
        string='Orientation (°)',
        help='Panel orientation in degrees (-180 to 180, 0=South)'
    )
    tilt_deg = fields.Float(
        string='Inclination (°)',
        help='Panel inclination in degrees (0-90)'
    )

    # Production Configuration
    annual_production_kwh = fields.Float(
        string='Annual Production (kWh)',
        required=True,
        help='Total yearly PV production in kWh (from Google Solar API, scaled to actual panel wattage)'
    )
    pvgis_annual_production_kwh = fields.Float(
        string='PVGIS Annual Production (kWh)',
        help='PVGIS calculated yearly production for comparison with Google Solar API'
    )
    production_profile_id = fields.Many2one(
        'pv.production.profile',
        string='Production Profile',
        required=True,
        help='Monthly percentage distribution profile for chart generation'
    )

    # Monthly Results (Required for chart generation)
    monthly_result_ids = fields.One2many(
        'pv.monthly.result',
        'simulation_id',
        string='Monthly Results',
        help='Monthly production values needed for chart on page 2'
    )

    # Chart Images
    chart_monthly_production = fields.Binary(
        string='Monthly Production Chart',
        help='PNG: Monthly daily production bar chart'
    )

    @api.model
    def create(self, vals_list):
        # Handle both single dict and list of dicts for backward compatibility
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('pv.simulation') or _('New')

        records = super(PvSimulation, self).create(vals_list)

        # Link back to sale order
        for record in records:
            if record.sale_order_id and not record.sale_order_id.pv_simulation_id:
                record.sale_order_id.pv_simulation_id = record.id

        return records

    @api.depends('sale_order_id.partner_id',
                 'sale_order_id.partner_id.street',
                 'sale_order_id.partner_id.street2',
                 'sale_order_id.partner_id.city',
                 'sale_order_id.partner_id.zip',
                 'sale_order_id.partner_id.country_id')
    def _compute_installation_address(self):
        """Auto-populate installation address from customer address"""
        for record in self:
            if not record.sale_order_id or not record.sale_order_id.partner_id:
                continue

            partner = record.sale_order_id.partner_id
            address_parts = []

            if partner.street:
                address_parts.append(partner.street)
            if partner.street2:
                address_parts.append(partner.street2)

            city_line = []
            if partner.zip:
                city_line.append(partner.zip)
            if partner.city:
                city_line.append(partner.city)
            if city_line:
                address_parts.append(' '.join(city_line))

            if partner.country_id and partner.country_id.name:
                address_parts.append(partner.country_id.name)

            if address_parts:
                record.installation_address = '\n'.join(address_parts)

    @api.depends('sale_order_id', 'sale_order_id.order_line', 'sale_order_id.order_line.product_id',
                 'sale_order_id.order_line.product_id.is_solar_panel',
                 'sale_order_id.order_line.product_id.panel_unit_power_wc',
                 'sale_order_id.order_line.product_uom_qty')
    def _compute_panel_data(self):
        """Calculate panel data from sale order line items"""
        for record in self:
            if not record.sale_order_id:
                record.number_of_panels = 0
                record.panel_unit_power_wc = 0.0
                record.total_pv_power_wc = 0.0
                continue

            # Find all solar panel products in the sale order
            panel_lines = record.sale_order_id.order_line.filtered(
                lambda l: l.product_id.is_solar_panel
            )

            if not panel_lines:
                record.number_of_panels = 0
                record.panel_unit_power_wc = 0.0
                record.total_pv_power_wc = 0.0
                continue

            # Sum quantities for total number of panels
            total_qty = sum(line.product_uom_qty for line in panel_lines)
            record.number_of_panels = int(total_qty)

            # Get unit power from the first panel product
            # (assumes all panels have the same unit power)
            first_panel = panel_lines[0]
            record.panel_unit_power_wc = first_panel.product_id.panel_unit_power_wc

            # Calculate total power
            record.total_pv_power_wc = record.number_of_panels * record.panel_unit_power_wc

    def action_regenerate_simulation(self):
        """Button action to fetch API data and recalculate everything"""
        self.ensure_one()

        # Fetch solar data from APIs (force update to replace existing values)
        self.action_fetch_solar_data(force_update=True)

        # Recalculate monthly results and charts
        self._compute_monthly_results()
        self._generate_charts()

        # Reload the page to show updated data
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_generate_report(self):
        """Generate PDF report (QWeb - default)"""
        self.ensure_one()
        return self.env.ref('bgg_pv_simulation.action_report_pv_simulation').report_action(self)


    def action_generate_report_weasyprint(self):
        """Generate PDF report using WeasyPrint"""
        self.ensure_one()

        # Generate PDF using WeasyPrint
        generator = self.env['pv.simulation.weasyprint.generator']
        pdf_content = generator.generate_report(self.id)

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'Report_WeasyPrint_{self.name}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'pv.simulation',
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })

        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def _compute_monthly_results(self):
        """
        Generate or update all 12 monthly result records
        Prioritizes PVGIS data if available, falls back to production profile
        """
        self.ensure_one()

        # First, try to use PVGIS data if we have the necessary inputs
        if self.latitude and self.longitude and self.total_pv_power_wc:
            _logger.info(f"🔄 Regenerating monthly results for {self.name} - checking for PVGIS data")

            # If we already have PVGIS data stored, use it
            if self.pvgis_annual_production_kwh and self.pvgis_annual_production_kwh > 0:
                _logger.info(f"✅ PVGIS data already available ({self.pvgis_annual_production_kwh:.0f} kWh) - preserving it")
                # PVGIS data already stored in monthly_result_ids, no need to regenerate
                # Just regenerate the charts
                return
            else:
                # Try to fetch fresh PVGIS data (without automatic fallback)
                _logger.info(f"📡 No existing PVGIS data - attempting to fetch from API")
                success = self._fetch_pvgis_monthly(fallback_to_profile=False)
                if success:
                    _logger.info(f"✅ Successfully fetched and stored PVGIS monthly data")
                    return
                else:
                    _logger.warning(f"⚠️ PVGIS fetch failed during regeneration")
                    # Fall through to production profile method

        # Fallback: Use production profile if PVGIS is not available
        _logger.info(f"📊 Using production profile fallback for monthly calculations")

        # Validate required profile
        if not self.production_profile_id:
            raise ValidationError(_('Production profile is required for chart generation'))

        # Use the production profile method
        self._compute_monthly_from_profile()

    def _generate_charts(self):
        """Generate all chart images for the simulation"""
        try:
            import warnings
            # Suppress matplotlib version conflict warning (harmless - we only use 2D plots)
            warnings.filterwarnings('ignore', message='Unable to import Axes3D')

            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
        except ImportError:
            _logger.warning(
                'Matplotlib library is not installed. Charts will not be generated. '
                'Install with: pip install matplotlib'
            )
            return  # Skip chart generation, don't raise error
        except Exception as e:
            _logger.warning(f'Matplotlib import error: {e}. Charts will not be generated.')
            return  # Skip chart generation

        for record in self:
            if not record.monthly_result_ids:
                continue

            try:
                record.chart_monthly_production = record._generate_monthly_production_chart()
            except Exception as e:
                _logger.error(f"Failed to generate chart for {record.name}: {e}")
                # Continue even if chart generation fails

    def _generate_monthly_production_chart(self):
        """Chart 1: Monthly daily production bar chart"""
        import matplotlib.pyplot as plt
        import io
        import base64

        # Use full month names in French
        fig, ax = plt.subplots(figsize=(10, 4))
        months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        # Sort by month number (convert string to int for proper ordering: 1,2,3...12 not 1,10,11,12,2,3...)
        values = [r.daily_production_kwh for r in self.monthly_result_ids.sorted(lambda r: int(r.month))]

        bars = ax.bar(months, values, color='#8BC34A')
        ax.set_ylabel('kWh', fontsize=10)
        # No title - it's shown as a separate section header in the report
        ax.grid(axis='y', alpha=0.3)

        # Remove ALL borders/spines for clean look
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)

        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45, ha='right', fontsize=9)

        # Add value labels on bars
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + (max(values) * 0.02),
                    f'{val:.1f}',
                    ha='center', va='bottom', fontsize=8)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none', transparent=False)
        plt.close()

        return base64.b64encode(buffer.getvalue())

    # ========================================
    # Solar API Integration Methods
    # ========================================
    #
    # DATA FLOW & HIERARCHY:
    #
    # 1. Google Solar API (action_fetch_solar_data):
    #    - Provides: Annual production, roof area, max panels, imagery
    #    - Automatically calls PVGIS for monthly breakdown
    #
    # 2. PVGIS API (_fetch_pvgis_monthly):
    #    - Provides: Monthly production values (12 months)
    #    - Stores data in monthly_result_ids
    #    - Preferred source for monthly data (more accurate than scaling)
    #
    # 3. Production Profile (_compute_monthly_from_profile):
    #    - Fallback method when PVGIS is unavailable
    #    - Uses percentage distribution applied to annual total
    #    - Less accurate than PVGIS but always available
    #
    # REGENERATION LOGIC (action_regenerate_simulation):
    #    - Priority 1: Preserve existing PVGIS data if available
    #    - Priority 2: Try to fetch fresh PVGIS data
    #    - Priority 3: Fall back to production profile
    #
    # ========================================

    def action_fetch_solar_data(self, force_update=False):
        """
        Fetch solar data from Google Solar API and populate fields
        This method is called from the UI button

        Args:
            force_update: If True, overwrite existing values. If False, only fill empty fields.
        """
        self.ensure_one()

        # Check if we have coordinates
        if not self.latitude or not self.longitude:
            raise UserError(_(
                "Please provide latitude and longitude coordinates first.\n"
                "You can get these from the installation address using a geocoding service."
            ))

        # Check if sale order has solar panels configured
        if not self.number_of_panels or not self.panel_unit_power_wc:
            missing = []
            if not self.number_of_panels:
                missing.append(_("- No solar panel products found on the sale order (products must have 'Is Solar Panel' checked)"))
            if not self.panel_unit_power_wc:
                missing.append(_("- Solar panel product has no power (Wc) specified"))
            raise UserError(_(
                "Cannot fetch solar data: the sale order is missing required solar panel information.\n\n"
                "%s\n\n"
                "Please ensure the sale order has at least one product marked as a solar panel "
                "with the power rating (Wc) properly configured."
            ) % '\n'.join(missing))

        # Get Solar API client
        solar_api = self.env['solar.api.client']

        try:
            # Fetch building insights
            api_response = solar_api.get_building_insights(
                latitude=self.latitude,
                longitude=self.longitude
            )

            # Parse the response and match to sale order panels
            parsed_data = solar_api.parse_building_insights(
                api_response,
                target_panels=self.number_of_panels,  # Match panel count to sale order
                target_panel_watts=self.panel_unit_power_wc,  # Scale production to actual panel wattage
                latitude=self.latitude,  # For Data Layers API fallback
                longitude=self.longitude  # For Data Layers API fallback
            )

            # Update fields with API data
            self._apply_solar_api_data(parsed_data, force_update=force_update)

            # Fetch monthly data from PVGIS
            self._fetch_pvgis_monthly()

            # Reload the page to show fetched data
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        except UserError:
            # Re-raise UserError (already formatted for display)
            raise
        except Exception as e:
            _logger.error(f"Failed to fetch solar data: {e}", exc_info=True)
            raise UserError(_(
                "Failed to fetch solar data from Google Solar API.\n"
                "Error: %s\n\n"
                "Please check:\n"
                "1. Your API key is configured correctly\n"
                "2. The Solar API is enabled in Google Cloud Console\n"
                "3. The coordinates are valid\n"
                "4. You have internet connectivity"
            ) % str(e))

    def _apply_solar_api_data(self, parsed_data, force_update=False):
        """
        Apply parsed Solar API data to simulation fields

        Args:
            parsed_data: dict from solar_api_client.parse_building_insights()
            force_update: If True, overwrite existing values. If False, only fill empty fields.
        """
        self.ensure_one()

        _logger.info(f"=== Applying Solar API data to simulation {self.name} (force_update={force_update}) ===")
        _logger.info(f"Parsed data keys: {list(parsed_data.keys())}")
        _logger.info(f"Has imagery: {bool(parsed_data.get('imagery_data'))}, "
                    f"Roof area: {parsed_data.get('roof_area_m2')}, "
                    f"Yearly energy: {parsed_data.get('yearly_energy_kwh')}, "
                    f"Monthly values: {len(parsed_data.get('monthly_energy_kwh', []))}")

        updates = {}

        # Update location image if available
        if parsed_data.get('imagery_data'):
            updates['location_image'] = base64.b64encode(parsed_data['imagery_data'])
            updates['location_image_filename'] = 'solar_api_imagery.png'
            _logger.info(f"Updated location imagery for simulation {self.name}")

        # Update roof area if available (for validation/comparison)
        if parsed_data.get('roof_area_m2'):
            api_roof_area = parsed_data['roof_area_m2']
            if not self.roof_surface_m2 or force_update:
                # Auto-populate if empty or force update
                updates['roof_surface_m2'] = api_roof_area
                _logger.info(f"Set roof area to {api_roof_area:.2f} m² from API (force={force_update})")
            else:
                # Log if different from user input
                diff_pct = abs(self.roof_surface_m2 - api_roof_area) / api_roof_area * 100
                if diff_pct > 10:
                    _logger.warning(
                        f"Roof area difference: User={self.roof_surface_m2:.2f} m², "
                        f"API={api_roof_area:.2f} m² ({diff_pct:.1f}% diff)"
                    )

        # Update max panels count if available
        if parsed_data.get('max_panels_count'):
            updates['max_panels_count'] = parsed_data['max_panels_count']
            _logger.info(f"Set max panels capacity to {parsed_data['max_panels_count']} panels from API")

        # Update annual production if available
        if parsed_data.get('yearly_energy_kwh'):
            api_production = parsed_data['yearly_energy_kwh']
            if not self.annual_production_kwh or force_update:
                # Auto-populate if empty or force update
                updates['annual_production_kwh'] = api_production
                _logger.info(f"Set annual production to {api_production:.0f} kWh from API (force={force_update})")
            else:
                # Log if different
                diff_pct = abs(self.annual_production_kwh - api_production) / api_production * 100
                if diff_pct > 20:
                    _logger.warning(
                        f"Production estimate difference: User={self.annual_production_kwh:.0f} kWh, "
                        f"API={api_production:.0f} kWh ({diff_pct:.1f}% diff)"
                    )

        # Update monthly production profile if available
        if parsed_data.get('monthly_energy_kwh') and len(parsed_data['monthly_energy_kwh']) == 12:
            monthly_values = parsed_data['monthly_energy_kwh']
            total_monthly = sum(monthly_values)

            if total_monthly > 0:
                # Calculate percentage distribution
                monthly_percentages = [(val / total_monthly * 100) for val in monthly_values]

                # Create or update production profile
                profile_name = f"API Profile - {self.name}"
                production_profile = self.env['pv.production.profile'].search([
                    ('name', '=', profile_name)
                ], limit=1)

                profile_vals = {
                    'name': profile_name,
                    'jan_percent': monthly_percentages[0],
                    'feb_percent': monthly_percentages[1],
                    'mar_percent': monthly_percentages[2],
                    'apr_percent': monthly_percentages[3],
                    'may_percent': monthly_percentages[4],
                    'jun_percent': monthly_percentages[5],
                    'jul_percent': monthly_percentages[6],
                    'aug_percent': monthly_percentages[7],
                    'sep_percent': monthly_percentages[8],
                    'oct_percent': monthly_percentages[9],
                    'nov_percent': monthly_percentages[10],
                    'dec_percent': monthly_percentages[11],
                }

                if production_profile:
                    production_profile.write(profile_vals)
                else:
                    production_profile = self.env['pv.production.profile'].create(profile_vals)

                updates['production_profile_id'] = production_profile.id
                _logger.info(f"Created/updated production profile from API monthly data")

        # Apply all updates
        if updates:
            self.write(updates)

        return True

    def _fetch_pvgis_monthly(self, fallback_to_profile=True):
        """
        Fetch monthly production data from PVGIS API and store in monthly_result_ids

        Args:
            fallback_to_profile: If True, falls back to production profile on failure.
                                If False, raises exception on failure.

        Returns:
            bool: True if PVGIS data was successfully fetched, False otherwise
        """
        self.ensure_one()

        # Check if we have required data for PVGIS
        if not self.latitude or not self.longitude or not self.total_pv_power_wc:
            missing_fields = []
            if not self.latitude:
                missing_fields.append('latitude')
            if not self.longitude:
                missing_fields.append('longitude')
            if not self.total_pv_power_wc:
                missing_fields.append('total_pv_power_wc (no solar panel with power rating on sale order)')
            _logger.warning("⚠️ Missing required data for PVGIS: %s", ', '.join(missing_fields))
            if fallback_to_profile:
                _logger.info("⚠️ Using production profile fallback")
                self._compute_monthly_from_profile()
            return False

        # Get Solar API client
        solar_api = self.env['solar.api.client']

        try:
            # Call PVGIS API
            pvgis_data = solar_api.get_pvgis_monthly(
                latitude=self.latitude,
                longitude=self.longitude,
                peakpower_kw=self.total_pv_power_wc / 1000.0,  # Convert Wc to kW
                angle=self.tilt_deg if self.tilt_deg else None,
                aspect=self.orientation_deg if self.orientation_deg else None
            )

            if not pvgis_data or not pvgis_data.get('monthly_kwh'):
                _logger.warning("⚠️ PVGIS returned no data")
                if fallback_to_profile:
                    _logger.info("⚠️ Using production profile fallback")
                    self._compute_monthly_from_profile()
                return False

            # Store PVGIS yearly total for comparison
            self.pvgis_annual_production_kwh = pvgis_data['yearly_kwh']
            _logger.info(f"📊 Comparison - Google: {self.annual_production_kwh:.0f} kWh vs PVGIS: {self.pvgis_annual_production_kwh:.0f} kWh")

            # Store monthly data
            self._store_monthly_results(pvgis_data['monthly_kwh'])
            return True

        except Exception as e:
            _logger.error(f"Failed to fetch PVGIS data: {e}")
            if fallback_to_profile:
                _logger.info("⚠️ Falling back to production profile")
                self._compute_monthly_from_profile()
            return False

    def _store_monthly_results(self, monthly_kwh_list):
        """
        Store monthly production values in monthly_result_ids

        Args:
            monthly_kwh_list: List of 12 monthly kWh values
        """
        self.ensure_one()

        if len(monthly_kwh_list) != 12:
            _logger.error(f"Expected 12 monthly values, got {len(monthly_kwh_list)}")
            return

        # Delete existing monthly results
        self.monthly_result_ids.unlink()

        # Days in each month
        days_in_months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        # Create new monthly results
        monthly_results = []
        for month_num in range(1, 13):
            monthly_kwh = monthly_kwh_list[month_num - 1]
            days = days_in_months[month_num - 1]
            daily_kwh = monthly_kwh / days

            monthly_result_vals = {
                'simulation_id': self.id,
                'month': str(month_num),
                'daily_production_kwh': daily_kwh,
            }
            monthly_results.append((0, 0, monthly_result_vals))

        self.monthly_result_ids = monthly_results
        _logger.info(f"✅ Stored {len(monthly_results)} monthly results from PVGIS")

    def _compute_monthly_from_profile(self):
        """
        Compute monthly results from production profile (fallback method)
        """
        self.ensure_one()

        if not self.production_profile_id:
            _logger.warning("⚠️ No production profile available")
            return

        _logger.info("📊 Computing monthly results from production profile (fallback)")

        # Delete existing monthly results
        self.monthly_result_ids.unlink()

        days_in_months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        monthly_results = []

        for month_num in range(1, 13):
            month_pct = self.production_profile_id.get_month_pct(month_num)
            monthly_production_kwh = self.annual_production_kwh * (month_pct / 100.0)
            days = days_in_months[month_num - 1]
            daily_production_kwh = monthly_production_kwh / days

            monthly_result_vals = {
                'simulation_id': self.id,
                'month': str(month_num),
                'daily_production_kwh': daily_production_kwh,
            }
            monthly_results.append((0, 0, monthly_result_vals))

        self.monthly_result_ids = monthly_results

    def action_fetch_solar_data_force(self):
        """
        Fetch solar data and OVERWRITE existing values
        Useful when you want to replace manual entries with API data
        """
        return self.action_fetch_solar_data(force_update=True)

    def action_clear_pvgis_data(self):
        """
        Clear PVGIS data to force regeneration from production profile
        Useful for testing or when you want to use production profile instead of PVGIS
        """
        self.ensure_one()
        _logger.info(f"🗑️ Clearing PVGIS data for simulation {self.name}")
        self.pvgis_annual_production_kwh = 0
        _logger.info(f"✅ PVGIS data cleared - next regeneration will use production profile")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('PVGIS Data Cleared'),
                'message': _('PVGIS data has been cleared. Click "Regenerate Simulation" to use production profile instead.'),
                'type': 'success',
                'sticky': False,
            }
        }
