# -*- coding: utf-8 -*-

import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from .product_template import _is_panel_category

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
        default=lambda self: self.env.company.pv_default_cover_photo,
        help='Cover page photo (configurable per quotation)'
    )
    cover_photo_filename = fields.Char(
        string='Cover Photo Filename',
        default=lambda self: self.env.company.pv_default_cover_photo_filename,
    )
    cover_title = fields.Char(
        string='Cover Title (Line 1)',
        default='Votre installation',
        help='First line of cover title (dark text)'
    )
    cover_subtitle = fields.Char(
        string='Cover Title (Line 2)',
        default='Photovoltaïque',
        help='Second line of cover title (green accent text)'
    )
    system_image = fields.Binary(
        string='System Image',
        default=lambda self: self.env.company.pv_default_system_image,
        help='Image displayed next to system characteristics (e.g. panel layout photo)'
    )
    system_image_filename = fields.Char(
        string='System Image Filename',
        default=lambda self: self.env.company.pv_default_system_image_filename,
    )

    # Section Titles (Configurable per Quotation)
    section_title_location = fields.Char(
        string='Location Section Title',
        default='LOCALISATION DE L\'INSTALLATION',
        help='Page 2: Installation location section'
    )
    section_title_system = fields.Char(
        string='System Section Title',
        default='CARACTÉRISTIQUES DU SYSTÈME',
        help='Page 3: System characteristics section'
    )
    section_title_production = fields.Char(
        string='Production Section Title',
        default='PRODUCTION ESTIMÉE',
        help='Page 3: Production section'
    )
    section_title_consumption = fields.Char(
        string='Consumption Data Section Title',
        default='DONNÉES DE CONSOMMATION',
        help='Page 4: Consumption data and energy balance section'
    )
    section_title_bilan = fields.Char(
        string='Energy Balance Section Title',
        default='BILAN ÉNERGÉTIQUE',
        help='Page 4: Annual energy balance section'
    )
    section_title_monthly_data = fields.Char(
        string='Monthly Data Subtitle',
        default='DONNÉES MENSUELLES',
        help='Page 4: Monthly data table subtitle'
    )
    section_title_daily_balance = fields.Char(
        string='Daily Energy Balance Subtitle',
        default='BILAN ÉNERGÉTIQUE QUOTIDIEN',
        help='Page 4: Daily energy balance table subtitle'
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
        string='Google Solar Annual Production (kWh)',
        help='Yearly PV production from Google Solar API (read-only reference value)'
    )
    pvgis_annual_production_kwh = fields.Float(
        string='Annual Production (kWh)',
        help='Yearly PV production from PVGIS — reference value used in the report'
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

    # Bilan (computed from monthly results)
    bilan_production_total = fields.Float(
        string='Production totale', compute='_compute_bilan', store=False)
    bilan_conso_day = fields.Float(
        string='Consommation jour', compute='_compute_bilan', store=False)
    bilan_conso_night = fields.Float(
        string='Consommation nuit', compute='_compute_bilan', store=False)
    bilan_conso_total = fields.Float(
        string='Consommation totale', compute='_compute_bilan', store=False)
    bilan_autocons_day = fields.Float(
        string='Autoconsommation jour', compute='_compute_bilan', store=False)
    bilan_battery_charge = fields.Float(
        string='Stocké batterie', compute='_compute_bilan', store=False)
    bilan_autocons_total = fields.Float(
        string='Autoconsommation totale', compute='_compute_bilan', store=False)
    bilan_savings_panels = fields.Float(
        string='Économies panneaux', compute='_compute_bilan', store=False)
    bilan_savings_battery = fields.Float(
        string='Économies batterie', compute='_compute_bilan', store=False)
    bilan_savings_resale = fields.Float(
        string='Économies revente', compute='_compute_bilan', store=False)
    bilan_savings_total = fields.Float(
        string='Total économies', compute='_compute_bilan', store=False)
    bilan_purchase_total = fields.Float(
        string='Coût achat', compute='_compute_bilan', store=False)

    # Chart Images
    chart_monthly_production = fields.Binary(
        string='Monthly Production Chart',
        help='PNG: Monthly daily production bar chart'
    )

    # Regeneration tracking
    simulation_needs_regeneration = fields.Boolean(
        string='Simulation Needs Regeneration',
        default=False,
        help='Set to True when simulation-impacting data has changed since last generation'
    )

    # Default consumption (to prefill monthly results)
    default_monthly_consumption_kwh = fields.Float(
        string='Consommation mensuelle par défaut (kWh)',
        help='Valeur de consommation mensuelle par défaut. Utilisez le bouton pour copier cette valeur sur tous les mois.'
    )
    default_daily_day_consumption_kwh = fields.Float(
        string='Consommation jour quotidienne par défaut (kWh)',
        help='Consommation de jour quotidienne par défaut. Utilisez le bouton pour copier cette valeur sur tous les mois.'
    )
    default_daily_night_consumption_kwh = fields.Float(
        string='Consommation nuit quotidienne par défaut (kWh)',
        help='Consommation de nuit quotidienne par défaut. Utilisez le bouton pour copier cette valeur sur tous les mois.'
    )

    # Fields whose change should flag the simulation for regeneration
    SIMULATION_IMPACTING_FIELDS = {
        'pvgis_annual_production_kwh',
        'orientation_deg',
        'tilt_deg',
        'production_profile_id',
        'latitude',
        'longitude',
        'roof_surface_m2',
    }

    def write(self, vals):
        res = super().write(vals)
        # If any simulation-impacting field changed, flag regeneration needed
        # Skip if we're already inside a regeneration to avoid re-flagging
        if self.SIMULATION_IMPACTING_FIELDS & set(vals.keys()):
            if not self.env.context.get('skip_regeneration_flag'):
                super().write({'simulation_needs_regeneration': True})
        return res

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

    @api.depends('monthly_result_ids', 'monthly_result_ids.monthly_production_kwh',
                 'monthly_result_ids.monthly_day_consumption_kwh',
                 'monthly_result_ids.monthly_night_consumption_kwh',
                 'monthly_result_ids.monthly_consumption_kwh',
                 'monthly_result_ids.monthly_autoconsumption_kwh',
                 'monthly_result_ids.monthly_battery_charge_kwh',
                 'monthly_result_ids.panel_savings',
                 'monthly_result_ids.battery_savings',
                 'monthly_result_ids.sale_revenue',
                 'monthly_result_ids.purchase_cost',
                 'pvgis_annual_production_kwh', 'annual_production_kwh')
    def _compute_bilan(self):
        for rec in self:
            results = rec.monthly_result_ids
            rec.bilan_production_total = rec.pvgis_annual_production_kwh or rec.annual_production_kwh or 0.0
            rec.bilan_conso_day = sum(results.mapped('monthly_day_consumption_kwh'))
            rec.bilan_conso_night = sum(results.mapped('monthly_night_consumption_kwh'))
            rec.bilan_conso_total = sum(results.mapped('monthly_consumption_kwh'))
            rec.bilan_autocons_total = sum(results.mapped('monthly_autoconsumption_kwh'))
            rec.bilan_battery_charge = sum(results.mapped('monthly_battery_charge_kwh'))
            rec.bilan_autocons_day = rec.bilan_autocons_total - rec.bilan_battery_charge
            rec.bilan_savings_panels = sum(results.mapped('panel_savings'))
            rec.bilan_savings_battery = sum(results.mapped('battery_savings'))
            rec.bilan_savings_resale = sum(results.mapped('sale_revenue'))
            rec.bilan_savings_total = rec.bilan_savings_panels + rec.bilan_savings_battery + rec.bilan_savings_resale
            rec.bilan_purchase_total = sum(results.mapped('purchase_cost'))

    def action_apply_default_consumption(self):
        """Copy default consumption values to all monthly results"""
        self.ensure_one()
        if not self.default_monthly_consumption_kwh and not self.default_daily_day_consumption_kwh and not self.default_daily_night_consumption_kwh:
            raise UserError(_("Veuillez saisir au moins une valeur de consommation par défaut."))
        if not self.monthly_result_ids:
            raise UserError(_("Aucun résultat mensuel trouvé. Veuillez d'abord générer la simulation."))

        days_in_months = {
            '1': 31, '2': 29, '3': 31, '4': 30, '5': 31, '6': 30,
            '7': 31, '8': 31, '9': 30, '10': 31, '11': 30, '12': 31
        }
        for result in self.monthly_result_ids:
            days = days_in_months.get(result.month, 30)
            vals = {}
            if self.default_monthly_consumption_kwh:
                vals['monthly_consumption_kwh'] = self.default_monthly_consumption_kwh
            if self.default_daily_day_consumption_kwh:
                vals['daily_day_consumption_kwh'] = self.default_daily_day_consumption_kwh
                vals['monthly_day_consumption_kwh'] = self.default_daily_day_consumption_kwh * days
            if self.default_daily_night_consumption_kwh:
                vals['daily_night_consumption_kwh'] = self.default_daily_night_consumption_kwh
                vals['monthly_night_consumption_kwh'] = self.default_daily_night_consumption_kwh * days
            if vals:
                result.write(vals)

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
                record.installation_address = False
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
                 'sale_order_id.order_line.product_id.categ_id',
                 'sale_order_id.order_line.product_id.panel_unit_power_wc',
                 'sale_order_id.order_line.product_uom_qty')
    def _compute_panel_data(self):
        """Calculate panel data from sale order line items.

        Panels are detected by product category: products under
        "All / Saleable / Panneaux" are considered solar panels.
        """
        for record in self:
            old_total = record.total_pv_power_wc

            if not record.sale_order_id:
                record.number_of_panels = 0
                record.panel_unit_power_wc = 0.0
                record.total_pv_power_wc = 0.0
            else:
                # Find all solar panel products by category
                panel_lines = record.sale_order_id.order_line.filtered(
                    lambda l: _is_panel_category(l.product_id)
                )

                if not panel_lines:
                    record.number_of_panels = 0
                    record.panel_unit_power_wc = 0.0
                    record.total_pv_power_wc = 0.0
                else:
                    # Sum quantities for total number of panels
                    total_qty = sum(line.product_uom_qty for line in panel_lines)
                    record.number_of_panels = int(total_qty)

                    # Get unit power from the first panel product
                    # (assumes all panels have the same unit power)
                    first_panel = panel_lines[0]
                    record.panel_unit_power_wc = first_panel.product_id.panel_unit_power_wc

                    # Calculate total power
                    record.total_pv_power_wc = record.number_of_panels * record.panel_unit_power_wc

            # Flag regeneration needed if total power changed
            if record.id and old_total and record.total_pv_power_wc != old_total:
                record.simulation_needs_regeneration = True

    def action_regenerate_simulation(self):
        """Button action: show loading screen then regenerate"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'pv_simulation_regenerate',
            'name': 'Régénération',
            'target': 'current',
            'context': {'simulation_id': self.id},
        }

    def action_do_regenerate(self):
        """Actual regeneration logic called from the JS client action"""
        self.ensure_one()

        # Use context flag to prevent write hook from re-flagging during regeneration
        self = self.with_context(skip_regeneration_flag=True)

        # Fetch solar data from APIs (force update to replace existing values)
        self.action_fetch_solar_data(force_update=True)

        # Recalculate monthly results and charts
        self._compute_monthly_results()
        self._generate_charts()

        # Clear regeneration flag
        self.simulation_needs_regeneration = False

    def action_generate_report(self):
        """Generate PDF report using WeasyPrint"""
        self.ensure_one()

        generator = self.env['pv.simulation.weasyprint.generator']
        pdf_content = generator.generate_report(self.id)

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'Rapport_PV_{self.name}.pdf',
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
            raise ValidationError(_('Un profil de production est requis pour la génération du graphique'))

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
                "Veuillez d'abord renseigner les coordonnées (latitude et longitude).\n"
                "Vous pouvez les obtenir à partir de l'adresse d'installation via un service de géocodage."
            ))

        # Check if sale order has solar panels configured
        if not self.number_of_panels or not self.panel_unit_power_wc:
            missing = []
            if not self.number_of_panels:
                missing.append(_("- Aucun produit panneau solaire trouvé sur le bon de commande "
                                 "(les produits doivent appartenir à la catégorie 'All / Saleable / Panneaux')"))
            if not self.panel_unit_power_wc:
                missing.append(_("- Le produit panneau solaire n'a pas de 'Puissance unitaire (Wc)' renseignée"))
            raise UserError(_(
                "Impossible de récupérer les données solaires : le bon de commande ne contient pas "
                "les informations requises sur les panneaux solaires.\n\n"
                "%s\n\n"
                "Veuillez vous assurer que le bon de commande contient au moins un produit dans la catégorie "
                "'All / Saleable / Panneaux' avec la 'Puissance unitaire (Wc)' correctement configurée."
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
                "Erreur lors de la récupération des données solaires depuis Google Solar API.\n"
                "Erreur : %s\n\n"
                "Veuillez vérifier :\n"
                "1. Votre clé API est correctement configurée\n"
                "2. L'API Solar est activée dans la console Google Cloud\n"
                "3. Les coordonnées sont valides\n"
                "4. Vous avez une connexion internet"
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

        # Days in each month (Feb = 29)
        days_in_months = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        # Create new monthly results
        monthly_results = []
        for month_num in range(1, 13):
            monthly_kwh = monthly_kwh_list[month_num - 1]
            days = days_in_months[month_num - 1]
            daily_kwh = monthly_kwh / days

            monthly_result_vals = {
                'simulation_id': self.id,
                'month': str(month_num),
                'monthly_production_kwh': monthly_kwh,
                'daily_production_kwh': daily_kwh,
            }
            # Auto-apply default consumption values
            if self.default_monthly_consumption_kwh:
                monthly_result_vals['monthly_consumption_kwh'] = self.default_monthly_consumption_kwh
            if self.default_daily_day_consumption_kwh:
                monthly_result_vals['daily_day_consumption_kwh'] = self.default_daily_day_consumption_kwh
                monthly_result_vals['monthly_day_consumption_kwh'] = self.default_daily_day_consumption_kwh * days
            if self.default_daily_night_consumption_kwh:
                monthly_result_vals['daily_night_consumption_kwh'] = self.default_daily_night_consumption_kwh
                monthly_result_vals['monthly_night_consumption_kwh'] = self.default_daily_night_consumption_kwh * days
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

        days_in_months = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        monthly_results = []

        for month_num in range(1, 13):
            month_pct = self.production_profile_id.get_month_pct(month_num)
            annual = self.pvgis_annual_production_kwh or self.annual_production_kwh or 0.0
            monthly_production_kwh = annual * (month_pct / 100.0)
            days = days_in_months[month_num - 1]
            daily_production_kwh = monthly_production_kwh / days

            monthly_result_vals = {
                'simulation_id': self.id,
                'month': str(month_num),
                'monthly_production_kwh': monthly_production_kwh,
                'daily_production_kwh': daily_production_kwh,
            }
            # Auto-apply default consumption values
            if self.default_monthly_consumption_kwh:
                monthly_result_vals['monthly_consumption_kwh'] = self.default_monthly_consumption_kwh
            if self.default_daily_day_consumption_kwh:
                monthly_result_vals['daily_day_consumption_kwh'] = self.default_daily_day_consumption_kwh
                monthly_result_vals['monthly_day_consumption_kwh'] = self.default_daily_day_consumption_kwh * days
            if self.default_daily_night_consumption_kwh:
                monthly_result_vals['daily_night_consumption_kwh'] = self.default_daily_night_consumption_kwh
                monthly_result_vals['monthly_night_consumption_kwh'] = self.default_daily_night_consumption_kwh * days
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
