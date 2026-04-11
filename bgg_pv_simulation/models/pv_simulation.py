# -*- coding: utf-8 -*-

import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from .product_template import _is_panel_category, _is_battery_category

_logger = logging.getLogger(__name__)


class PvSimulation(models.Model):
    _name = 'pv.simulation'
    _description = 'Simulation PV'
    _order = 'create_date desc'

    # Core Fields
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Devis',
        required=True,
        ondelete='restrict'
    )
    partner_id = fields.Many2one(
        related='sale_order_id.partner_id',
        string='Client',
        readonly=True,
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company
    )
    installation_address = fields.Text(
        string="Adresse d'installation",
        compute='_compute_installation_address',
        help="Adresse d'installation (issue de l'adresse client, lecture seule)"
    )
    latitude = fields.Char(
        string='Latitude',
    )
    longitude = fields.Char(
        string='Longitude',
    )
    google_maps_url = fields.Char(
        string='Google Maps',
        compute='_compute_google_maps_url',
    )
    location_image = fields.Binary(
        string='Image de localisation',
        help="Image satellite ou carte de l'emplacement d'installation"
    )
    location_image_filename = fields.Char(
        string="Nom du fichier image"
    )
    report_date = fields.Date(
        string='Date du rapport',
        default=fields.Date.today
    )

    # Cover Page Customization
    cover_photo = fields.Binary(
        string='Photo de couverture',
        help='Photo de couverture. Si vide, la photo par défaut (Configuration → Paramètres du rapport) est utilisée.',
    )
    cover_photo_filename = fields.Char(
        string='Nom du fichier photo de couverture',
    )
    cover_title = fields.Char(
        string='Titre de couverture (ligne 1)',
        default='Votre installation',
        help='Première ligne du titre de couverture (texte sombre)'
    )
    cover_subtitle = fields.Char(
        string='Titre de couverture (ligne 2)',
        default='Photovoltaïque',
        help='Deuxième ligne du titre de couverture (accent vert)'
    )
    system_image = fields.Binary(
        string='Image du système',
        help="Image système. Si vide, l'image par défaut (Configuration → Paramètres du rapport) est utilisée.",
    )
    system_image_filename = fields.Char(
        string='Nom du fichier image système',
    )

    # Section Titles (Configurable per Quotation)
    section_title_location = fields.Char(
        string='Titre de section — Localisation',
        default='LOCALISATION DE L\'INSTALLATION',
        help='Page Localisation : titre de la section'
    )
    section_title_system = fields.Char(
        string='Titre de section — Système',
        default='CARACTÉRISTIQUES DU SYSTÈME',
        help='Page Production : titre de la section caractéristiques du système'
    )
    section_title_production = fields.Char(
        string='Titre de section — Production',
        default='PRODUCTION ESTIMÉE',
        help='Page Production : titre principal'
    )
    section_title_consumption = fields.Char(
        string='Titre de section — Consommation',
        default='DONNÉES DE CONSOMMATION',
        help='Page Consommation : titre de la section données de consommation'
    )
    section_title_bilan = fields.Char(
        string='Titre de section — Bilan énergétique',
        default='BILAN ÉNERGÉTIQUE',
        help='Page Bilan énergétique annuel : titre de la section'
    )
    section_title_bilan_annuel = fields.Char(
        string='Titre de section — Bilan annuel',
        default='BILAN ANNUEL',
        help='Page Bilan annuel : titre principal (graphiques Production vs Consommation et répartition énergétique)'
    )
    section_title_bilan_annuel_prod_vs_conso = fields.Char(
        string='Sous-titre — Production vs Consommation',
        default='Production vs Consommation',
        help='Page BILAN ANNUEL : sous-titre du graphique Production vs Consommation'
    )
    section_title_bilan_annuel_repartition = fields.Char(
        string='Sous-titre — Répartition énergétique',
        default='Répartition énergétique',
        help='Page BILAN ANNUEL : sous-titre du graphique en anneau (répartition énergétique)'
    )
    section_title_monthly_data = fields.Char(
        string='Sous-titre — Données mensuelles',
        default='DONNÉES MENSUELLES / QUOTIDIENNES',
        help='Page Consommation : sous-titre du tableau des données mensuelles'
    )
    section_title_daily_balance = fields.Char(
        string='Sous-titre — Bilan énergétique quotidien',
        default='BILAN ÉNERGÉTIQUE QUOTIDIEN',
        help='Page Consommation : sous-titre du tableau du bilan énergétique quotidien'
    )

    # PV System Parameters
    roof_surface_m2 = fields.Float(
        string='Surface de toiture (m²)',
        help='Surface de toiture disponible en m²'
    )
    number_of_panels = fields.Integer(
        string='Nombre de panneaux',
        compute='_compute_panel_data',
        store=True,
        help='Nombre total de panneaux solaires (issu des lignes du devis)'
    )
    max_panels_count = fields.Integer(
        string='Panneaux maximum (capacité toiture)',
        help='Nombre maximum de panneaux que la toiture peut accueillir (source : Google Solar API)'
    )
    panel_unit_power_wc = fields.Float(
        string='Puissance unitaire (Wc)',
        compute='_compute_panel_data',
        store=True,
        help='Puissance par panneau en Wc (issue de la fiche produit)'
    )
    total_pv_power_wc = fields.Float(
        string='Puissance PV totale (Wc)',
        compute='_compute_panel_data',
        store=True,
        help='Puissance PV installée en Wc (calculée : nombre de panneaux × puissance unitaire)'
    )
    orientation_deg = fields.Float(
        string='Orientation (°)',
        help='Orientation des panneaux en degrés (-180 à 180, 0 = Sud)'
    )
    tilt_deg = fields.Float(
        string='Inclinaison (°)',
        help='Inclinaison des panneaux en degrés (0 à 90)'
    )

    # Battery Parameters (auto-detected from sale order)
    battery_capacity_kwh = fields.Float(
        string='Capacité batterie (kWh)',
        compute='_compute_battery_data',
        store=True,
        help='Capacité utile de la batterie en kWh (issue de la fiche produit)'
    )
    battery_efficiency = fields.Float(
        string='Rendement batterie (%)',
        compute='_compute_battery_data',
        store=True,
        help='Rendement aller-retour de la batterie en pourcentage (issu de la fiche produit)'
    )

    # Production Configuration
    annual_production_kwh = fields.Float(
        string='Production annuelle Google Solar (kWh)',
        help='Production annuelle PV estimée par Google Solar API (valeur de référence, lecture seule)'
    )
    pvgis_annual_production_kwh = fields.Float(
        string='Production annuelle (kWh)',
        help='Production annuelle PV issue de PVGIS — valeur de référence utilisée dans le rapport'
    )
    production_profile_id = fields.Many2one(
        'pv.production.profile',
        string='Profil de production',
        required=True,
        default=lambda self: self.env['pv.production.profile'].search([], limit=1),
        help='Profil de répartition mensuelle (%) utilisé pour la génération du graphique de production'
    )

    # Monthly Results (Required for chart generation)
    monthly_result_ids = fields.One2many(
        'pv.monthly.result',
        'simulation_id',
        string='Résultats mensuels',
        help='Valeurs de production mensuelle nécessaires au graphique de la page Production'
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
        string='Graphique — Production mensuelle',
        help='PNG : graphique en barres de la production quotidienne par mois'
    )
    chart_production_vs_consumption = fields.Binary(
        string='Graphique — Production vs Consommation',
        help='PNG : production quotidienne vs consommation avec superpositions bilan/revente/achat'
    )
    chart_energy_balance = fields.Binary(
        string='Graphique — Répartition énergétique (anneau)',
        help='PNG : graphique en anneau du bilan énergétique annuel — Production (Autoconso + Vente) vs Consommation (Autoconso + Achat)'
    )

    # Regeneration tracking
    simulation_needs_regeneration = fields.Boolean(
        string='Régénération nécessaire',
        default=False,
        help='Passe à Vrai lorsqu\'une donnée impactant la simulation a changé depuis la dernière génération'
    )
    version = fields.Integer(
        string='Version',
        default=1,
        readonly=True,
        copy=False,
        help='Numéro de version de cette simulation. Démarre à 1 (v01) et '
             's\'incrémente à chaque clic sur « Régénérer la simulation ».'
    )

    # Tariff profile for financial calculations. The profile is only used as
    # a starting point: when it is selected, its values are copied onto the
    # simulation's own override fields below so the user can adjust them per
    # simulation without altering the shared profile.
    tariff_profile_id = fields.Many2one(
        'pv.tariff.profile',
        string='Profil tarifaire',
        default=lambda self: self.env['pv.tariff.profile'].search([], limit=1),
        help='Profil tarifaire utilisé pour pré-remplir le bilan financier '
             '(prix d\'achat, tarif de revente, coût batterie). Les valeurs '
             'sont copiées sur la simulation et peuvent être modifiées sans '
             'impacter le profil de référence.'
    )
    purchase_price_kwh = fields.Float(
        string="Prix d'achat (€/kWh)",
        digits=(8, 2),
        help="Prix d'achat de l'électricité au réseau (P_buy). "
             "Pré-rempli depuis le profil tarifaire, modifiable par simulation."
    )
    feed_in_tariff_kwh = fields.Float(
        string='Tarif de revente (€/kWh)',
        digits=(8, 2),
        help="Tarif de revente du surplus PV au réseau (P_sell). "
             "Pré-rempli depuis le profil tarifaire, modifiable par simulation."
    )
    battery_cost_kwh = fields.Float(
        string="Coût batterie (€/kWh)",
        digits=(8, 2),
        help="Coût d'usure par kWh cyclé dans la batterie (P_batt). "
             "Pré-rempli depuis le profil tarifaire, modifiable par simulation."
    )

    @api.onchange('tariff_profile_id')
    def _onchange_tariff_profile_id(self):
        """Copy the selected profile's values onto the simulation so the user
        can override them locally without touching the shared profile."""
        for rec in self:
            profile = rec.tariff_profile_id
            if profile:
                rec.purchase_price_kwh = profile.purchase_price_kwh
                rec.feed_in_tariff_kwh = profile.feed_in_tariff_kwh
                rec.battery_cost_kwh = profile.battery_cost_kwh

    # Report section title for financial page
    section_title_financial = fields.Char(
        string='Titre — Bilan financier mensuel',
        default='BILAN FINANCIER MENSUEL',
        help='Titre de la page Bilan financier mensuel dans le rapport PDF'
    )
    report_company_name = fields.Char(
        string='Nom de société (rapport)',
        default='BelGoGreen',
        help='Nom de société affiché dans le pied de page du rapport PDF.'
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
    day_consumption_ratio = fields.Float(
        string='Ratio consommation jour (%)',
        default=0.6,
        help='Part de la consommation totale consommée en journée (0.0–1.0). '
             'Ex: 0.6 = 60 % jour, 40 % nuit. Utilisé pour dériver automatiquement '
             'les consommations jour/nuit à partir de la consommation mensuelle.'
    )

    # Fields whose change should flag the simulation for regeneration
    @staticmethod
    def _parse_coord(value):
        """Parse a coordinate string to float, accepting both dot and comma as decimal separator."""
        if not value or not str(value).strip():
            return 0.0
        cleaned = str(value).strip().replace(',', '.')
        parts = cleaned.split('.')
        if len(parts) > 2:
            cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _get_lat_lng(self):
        """Return (latitude, longitude) as floats, parsed from Char fields."""
        return self._parse_coord(self.latitude), self._parse_coord(self.longitude)

    SIMULATION_IMPACTING_FIELDS = {
        'pvgis_annual_production_kwh',
        'orientation_deg',
        'tilt_deg',
        'production_profile_id',
        'latitude',
        'longitude',
        'roof_surface_m2',
        'tariff_profile_id',
        'purchase_price_kwh',
        'feed_in_tariff_kwh',
        'battery_cost_kwh',
    }

    def write(self, vals):
        res = super().write(vals)
        # If any simulation-impacting field changed, flag regeneration needed
        # Skip if we're already inside a regeneration to avoid re-flagging
        if self.SIMULATION_IMPACTING_FIELDS & set(vals.keys()):
            if not self.env.context.get('skip_regeneration_flag'):
                super().write({'simulation_needs_regeneration': True})
        return res

    @staticmethod
    def _format_simulation_name(so_ref, version):
        """Build the SIM-<SO>-vNN reference string for a given version."""
        return f'SIM-{so_ref}-v{int(version or 1):02d}'

    @api.model
    def _next_simulation_reference(self, sale_order=None, version=1):
        """Return the next simulation reference.

        Preferred format: ``SIM-<sale order reference>-v<NN>`` where NN is
        the generation version. Newly created simulations start at v01;
        the version is then incremented every time the user regenerates
        the simulation from the UI. If no sale order is provided, falls
        back to the legacy global sequence so callers that don't know the
        SO still get a unique reference.
        """
        if sale_order and sale_order.name:
            return self._format_simulation_name(sale_order.name, version)

        # Legacy fallback — keep the sequence path so older call sites
        # (and test fixtures) that create simulations without a sale order
        # still receive a unique reference.
        Sequence = self.env['ir.sequence'].sudo()
        new_name = Sequence.next_by_code('pv.simulation')
        if new_name:
            return new_name
        # Sequence record missing — create it now so future calls succeed.
        existing = Sequence.search([('code', '=', 'pv.simulation')], limit=1)
        if not existing:
            Sequence.create({
                'name': 'PV Simulation Sequence',
                'code': 'pv.simulation',
                'prefix': 'SIM-',
                'padding': 5,
                'number_next': 1,
                'number_increment': 1,
            })
            new_name = Sequence.next_by_code('pv.simulation')
            if new_name:
                return new_name
        # Hard fallback so we never persist the placeholder 'New' label.
        return 'SIM-' + fields.Datetime.now().strftime('%Y%m%d%H%M%S')

    @api.model_create_multi
    def create(self, vals_list):
        placeholder_names = {'New', _('New')}
        default_tariff = self.env['pv.tariff.profile'].search([], limit=1)
        for vals in vals_list:
            current = vals.get('name')
            if not current or current in placeholder_names:
                so_id = vals.get('sale_order_id')
                sale_order = self.env['sale.order'].browse(so_id) if so_id else None
                vals['name'] = self._next_simulation_reference(sale_order=sale_order)
            # Seed the per-simulation tariff overrides from the selected
            # profile when they are not explicitly provided (the @api.onchange
            # only fires from the UI, not from programmatic creates).
            # If no profile was supplied at all, fall back to the first
            # tariff profile found so new simulations always land with
            # sensible default prices pre-filled.
            profile_id = vals.get('tariff_profile_id')
            if not profile_id and default_tariff:
                vals['tariff_profile_id'] = default_tariff.id
                profile_id = default_tariff.id
            if profile_id:
                profile = self.env['pv.tariff.profile'].browse(profile_id)
                if profile.exists():
                    vals.setdefault('purchase_price_kwh', profile.purchase_price_kwh)
                    vals.setdefault('feed_in_tariff_kwh', profile.feed_in_tariff_kwh)
                    vals.setdefault('battery_cost_kwh', profile.battery_cost_kwh)
        return super().create(vals_list)

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

    def _apply_consumption_ratio(self, monthly_kwh, days, ratio=None):
        """Derive day/night consumption values from a monthly total using the ratio.

        Returns a dict with all consumption fields ready to write on a monthly result.
        """
        if ratio is None:
            ratio = self.day_consumption_ratio or 0.6
        if ratio <= 0 or ratio >= 1:
            ratio = 0.6
        daily_total = monthly_kwh / days if days else 0.0
        return {
            'monthly_consumption_kwh': round(monthly_kwh, 2),
            'daily_day_consumption_kwh': round(daily_total * ratio, 2),
            'daily_night_consumption_kwh': round(daily_total * (1 - ratio), 2),
            'monthly_day_consumption_kwh': round(monthly_kwh * ratio, 2),
            'monthly_night_consumption_kwh': round(monthly_kwh * (1 - ratio), 2),
        }

    @staticmethod
    def _distribute_annual_consumption(annual_kwh, count=12):
        """Split an annual consumption total across ``count`` months with
        cent-level precision.

        Each per-month value has at most 2 decimals and the sum of the
        returned values equals the original annual total exactly. This
        avoids the "5000 → 5000.04" drift caused by rounding ``annual / 12``
        independently for every month (round(416.666…, 2) = 416.67 →
        12 × 416.67 = 5000.04).
        """
        if not annual_kwh or count <= 0:
            return [0.0] * max(count, 0)
        total_cents = int(round(annual_kwh * 100))
        base_cents = total_cents // count
        extra = total_cents - base_cents * count
        return [
            (base_cents + (1 if i < extra else 0)) / 100.0
            for i in range(count)
        ]

    def action_apply_default_consumption(self):
        """Copy default monthly consumption to all months and derive day/night via ratio."""
        self.ensure_one()
        if not self.default_monthly_consumption_kwh:
            raise UserError(_("Veuillez saisir une valeur de consommation mensuelle par défaut."))
        if not self.monthly_result_ids:
            raise UserError(_("Aucun résultat mensuel trouvé. Veuillez d'abord générer la simulation."))

        # Distribute the implied annual total (monthly default × 12) across
        # the 12 months with cent-level precision so the sum on the bilan
        # page matches what the user entered in the wizard (5000, not 5000.04).
        annual_total = self.default_monthly_consumption_kwh * 12
        monthly_distribution = self._distribute_annual_consumption(annual_total, 12)
        sorted_results = self.monthly_result_ids.sorted(key=lambda r: int(r.month))
        for idx, result in enumerate(sorted_results):
            days = result.days_in_month or 30
            month_conso = monthly_distribution[idx] if idx < len(monthly_distribution) else self.default_monthly_consumption_kwh
            vals = self._apply_consumption_ratio(month_conso, days)
            result.write(vals)

        # Auto-compute daily energy balance after applying consumption
        self.action_compute_daily_balance()

    def action_apply_ratio(self):
        """Derive day/night from each month's existing monthly_consumption_kwh using the ratio."""
        self.ensure_one()
        if not self.monthly_result_ids:
            raise UserError(_("Aucun résultat mensuel trouvé. Veuillez d'abord générer la simulation."))

        for result in self.monthly_result_ids:
            monthly = result.monthly_consumption_kwh or 0.0
            if not monthly:
                continue
            days = result.days_in_month or 30
            vals = self._apply_consumption_ratio(monthly, days)
            del vals['monthly_consumption_kwh']  # keep existing value untouched
            result.write(vals)

        # Auto-compute daily energy balance after applying ratio
        self.action_compute_daily_balance()

    def action_compute_daily_balance(self):
        """Compute the daily energy balance (Charge, Vente, Achat) for all months.

        Uses the formulas:
        - SurplusPV = max(0, Production - Conso jour)
        - Autoconso jour = min(Production, Conso jour)
        - Charge = min(SurplusPV, CapBat × RenBat)
        - Vente = SurplusPV - Charge
        - CapDebutBat(M) = max(0, min(CapBat × RenBat, CapDebutBat(M-1) + Charge(M-1) - ConsoNuit(M-1)))
        - Énergie_batterie_nuit = min(CapDebutBat + Charge, CapBat × RenBat)
        - Achat = max(0, ConsoNuit - Énergie_batterie_nuit) + max(0, ConsoJour - Production)
        """
        self.ensure_one()
        if not self.monthly_result_ids:
            raise UserError(_("Aucun résultat mensuel trouvé. Veuillez d'abord générer la simulation."))

        cap_bat = self.battery_capacity_kwh or 0.0
        ren_bat = (self.battery_efficiency or 0.0) / 100.0  # stored as percentage
        cap_bat_effective = cap_bat * ren_bat  # CapBat × RenBat

        # Pricing — use the per-simulation overrides (seeded from the
        # selected tariff profile) so users can tweak prices without
        # touching the shared profile. Fall back to the profile if a
        # value is missing (e.g. records created before this field).
        tariff = self.tariff_profile_id
        p_buy = self.purchase_price_kwh or (tariff.purchase_price_kwh if tariff else 0.0)
        p_sell = self.feed_in_tariff_kwh or (tariff.feed_in_tariff_kwh if tariff else 0.0)
        p_batt = self.battery_cost_kwh or (tariff.battery_cost_kwh if tariff else 0.0)

        # Process months in order (1-12)
        results = self.monthly_result_ids.sorted(key=lambda r: int(r.month))
        cap_debut_bat = 0.0  # Battery starts empty

        for result in results:
            prod = result.daily_production_kwh or 0.0
            days = result.days_in_month or 30

            # If monthly consumption is set but day/night not yet derived, apply ratio
            if result.monthly_consumption_kwh and not result.daily_day_consumption_kwh and not result.daily_night_consumption_kwh:
                cons_vals = self._apply_consumption_ratio(result.monthly_consumption_kwh, days)
                result.write(cons_vals)

            conso_jour = result.daily_day_consumption_kwh or 0.0
            conso_nuit = result.daily_night_consumption_kwh or 0.0

            # SurplusPV
            surplus_pv = max(0.0, prod - conso_jour)
            # Autoconsommation jour
            autocons_jour = min(prod, conso_jour)
            # Charge batterie
            charge = min(surplus_pv, cap_bat_effective) if cap_bat > 0 else 0.0
            # Vente (surplus that can't be stored)
            vente = surplus_pv - charge
            # Énergie batterie disponible la nuit
            energie_bat_nuit = min(cap_debut_bat + charge, cap_bat_effective) if cap_bat > 0 else 0.0
            # Achat — cover the nighttime deficit from the battery shortfall
            # PLUS any daytime consumption not covered by production.
            achat = max(0.0, conso_nuit - energie_bat_nuit) + max(0.0, conso_jour - prod)

            # Financial calculations
            # Économie panneaux = Auto_jour_day * days * P_buy
            eco_panneaux = round(autocons_jour * days * p_buy, 2)
            # Vente surplus = vente * days * P_sell
            revenu_vente = round(vente * days * p_sell, 2)
            # Économie batterie = min(énergie_bat_nuit, ConsoNuit) * days * (P_buy - P_batt)
            batt_use = min(energie_bat_nuit, conso_nuit) if cap_bat > 0 else 0.0
            eco_batterie = round(batt_use * days * (p_buy - p_batt), 2)
            # Achat réseau = achat * days * P_buy
            cout_achat = round(achat * days * p_buy, 2)

            result.write({
                'daily_surplus_pv_kwh': round(surplus_pv, 2),
                'daily_day_autoconsumption_kwh': round(autocons_jour, 2),
                'daily_battery_charge_kwh': round(charge, 2),
                'daily_energy_sold_kwh': round(vente, 2),
                'daily_energy_bought_kwh': round(achat, 2),
                # Monthly totals
                'monthly_battery_charge_kwh': round(charge * days, 2),
                'monthly_energy_sold_kwh': round(vente * days, 2),
                'monthly_energy_bought_kwh': round(achat * days, 2),
                'monthly_autoconsumption_kwh': round((autocons_jour + batt_use) * days, 2),
                # Financial
                'panel_savings': eco_panneaux,
                'sale_revenue': revenu_vente,
                'battery_savings': eco_batterie,
                'purchase_cost': cout_achat,
                'net_balance': cout_achat - revenu_vente,
            })

            # CapDebutBat for next month: battery only discharges what was actually used (batt_use)
            cap_debut_bat = max(0.0, min(cap_bat_effective, cap_debut_bat + charge - batt_use))

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

    @api.depends('latitude', 'longitude')
    def _compute_google_maps_url(self):
        for rec in self:
            if rec.latitude and rec.longitude:
                lat = str(rec.latitude).strip().replace(',', '.')
                lng = str(rec.longitude).strip().replace(',', '.')
                rec.google_maps_url = 'https://www.google.com/maps?q=%s,%s' % (lat, lng)
            else:
                rec.google_maps_url = ''

    def action_open_google_maps(self):
        """Open the Google Maps URL for the current simulation in a new tab."""
        self.ensure_one()
        if not self.google_maps_url:
            raise UserError(_("Aucune coordonnée disponible. Récupérez d'abord les coordonnées GPS."))
        return {
            'type': 'ir.actions.act_url',
            'url': self.google_maps_url,
            'target': 'new',
        }

    def action_fetch_coordinates(self):
        """Fetch GPS coordinates from Google Geocoding API via geo.cache."""
        self.ensure_one()
        partner = self.sale_order_id.partner_id
        if not partner:
            raise UserError(_("Aucun client associé au devis."))

        # Delegate to wizard's geocoding logic
        Wizard = self.env['pv.simulation.wizard']
        lat, lng = Wizard._geocode_address(partner)
        if lat and lng:
            # Cache in geo.cache
            cache = self.env['geo.cache'].search([('partner_id', '=', partner.id)], limit=1)
            address_parts = [
                partner.street or '', partner.street2 or '',
                partner.zip or '', partner.city or '',
                partner.country_id.name or '',
            ]
            cache_vals = {
                'latitude': str(lat),
                'longitude': str(lng),
                'address': ', '.join(p for p in address_parts if p),
            }
            if cache:
                cache.write(cache_vals)
            else:
                cache_vals['partner_id'] = partner.id
                self.env['geo.cache'].create(cache_vals)
            self.write({
                'latitude': str(lat),
                'longitude': str(lng),
            })
        else:
            raise UserError(_(
                "Impossible de récupérer les coordonnées GPS pour l'adresse:\n%s\n\n"
                "Vérifiez que:\n"
                "- L'adresse du client est correcte\n"
                "- La clé API Google est configurée (google_api_key)\n"
                "- L'API Geocoding est activée dans la console Google Cloud"
            ) % self.installation_address)

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

    @api.depends('sale_order_id', 'sale_order_id.order_line', 'sale_order_id.order_line.product_id',
                 'sale_order_id.order_line.product_id.categ_id',
                 'sale_order_id.order_line.product_id.battery_capacity_kwh',
                 'sale_order_id.order_line.product_id.battery_efficiency_percent')
    def _compute_battery_data(self):
        """Calculate battery data from sale order line items.

        Batteries are detected by product category: products under
        "All / Saleable / Batteries" are considered batteries.
        """
        for record in self:
            if not record.sale_order_id:
                record.battery_capacity_kwh = 0.0
                record.battery_efficiency = 0.0
            else:
                battery_lines = record.sale_order_id.order_line.filtered(
                    lambda l: _is_battery_category(l.product_id)
                )
                if not battery_lines:
                    record.battery_capacity_kwh = 0.0
                    record.battery_efficiency = 0.0
                else:
                    # Sum capacity across all battery products × quantity
                    total_capacity = sum(
                        line.product_id.battery_capacity_kwh * line.product_uom_qty
                        for line in battery_lines
                    )
                    record.battery_capacity_kwh = total_capacity
                    # Use efficiency from the first battery product
                    record.battery_efficiency = battery_lines[0].product_id.battery_efficiency_percent

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

    def action_do_generate(self):
        """Initial generation logic called from the wizard JS client action.

        Creates monthly results, applies default consumption (if provided),
        then computes balance. Missing consumption data is not a hard error
        here: the user can fill it in afterwards on the Consommation tab.
        """
        self.ensure_one()
        # The wizard already created the record at v01 — the first
        # generation should not bump it to v02, so skip the version
        # increment on this initial pass.
        self.with_context(skip_version_bump=True).action_do_regenerate()
        if self.default_monthly_consumption_kwh:
            self.action_apply_default_consumption()
        self.action_compute_daily_balance()

    def _bump_version(self):
        """Increment the version number and refresh the SIM-<SO>-vNN name."""
        self.ensure_one()
        new_version = (self.version or 1) + 1
        so_ref = self.sale_order_id.name or 'DRAFT'
        new_name = self._format_simulation_name(so_ref, new_version)
        self.with_context(skip_regeneration_flag=True).write({
            'version': new_version,
            'name': new_name,
        })

    def action_do_regenerate(self):
        """Actual regeneration logic called from the JS client action"""
        self.ensure_one()

        # Use context flag to prevent write hook from re-flagging during regeneration
        self = self.with_context(skip_regeneration_flag=True)

        # Preserve existing per-month consumption values before regeneration
        # so they are not lost or re-applied from defaults
        saved_consumption = {}
        for result in self.monthly_result_ids:
            saved_consumption[result.month] = {
                'monthly_consumption_kwh': result.monthly_consumption_kwh,
                'daily_day_consumption_kwh': result.daily_day_consumption_kwh,
                'daily_night_consumption_kwh': result.daily_night_consumption_kwh,
                'monthly_day_consumption_kwh': result.monthly_day_consumption_kwh,
                'monthly_night_consumption_kwh': result.monthly_night_consumption_kwh,
            }

        # Fetch solar data from APIs (force update to replace existing values)
        self.action_fetch_solar_data(force_update=True)

        # Recalculate monthly results
        self._compute_monthly_results()

        # Restore saved consumption values to the newly created monthly results
        if saved_consumption:
            for result in self.monthly_result_ids:
                if result.month in saved_consumption:
                    result.write(saved_consumption[result.month])

        # Compute daily energy balance (Charge, Vente, Achat) BEFORE charts
        # so the Production vs Consommation chart can read the freshly
        # written daily_energy_sold_kwh / daily_energy_bought_kwh values.
        self.action_compute_daily_balance()

        # Now build the chart images from the up-to-date monthly results.
        self._generate_charts()

        # Clear regeneration flag
        self.simulation_needs_regeneration = False

        # Bump the version (and refresh the SIM-<SO>-vNN name) so the user
        # can tell regenerations apart. The initial wizard generation sets
        # ``skip_version_bump`` so the freshly-created simulation stays at
        # v01 after its very first run.
        if not self.env.context.get('skip_version_bump'):
            self._bump_version()

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
        lat, lng = self._get_lat_lng()
        if lat and lng and self.total_pv_power_wc:
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

            try:
                record.chart_production_vs_consumption = record._generate_production_vs_consumption_chart()
            except Exception as e:
                _logger.error(
                    f"Failed to generate production-vs-consumption chart for {record.name}: {e}"
                )

            try:
                record.chart_energy_balance = record._generate_energy_balance_chart()
            except Exception as e:
                _logger.error(
                    f"Failed to generate energy balance chart for {record.name}: {e}"
                )

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

    def _generate_production_vs_consumption_chart(self):
        """Chart 2: Production vs Consommation (daily averages per month).

        - Two columns per month side by side: production (single bar)
          and consumption (jour+nuit stacked).
        - Three overlays: Bilan (line, daily net energy), Revente (line,
          daily energy sold), Achat (filled area, plotted negatively).
        """
        import matplotlib.pyplot as plt
        import numpy as np
        import io
        import base64

        results = self.monthly_result_ids.sorted(key=lambda r: int(r.month))
        if not results:
            return False

        months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        production = [r.daily_production_kwh or 0.0 for r in results]
        cons_day = [r.daily_day_consumption_kwh or 0.0 for r in results]
        cons_night = [r.daily_night_consumption_kwh or 0.0 for r in results]
        bilan = [p - d - n for p, d, n in zip(production, cons_day, cons_night)]
        revente = [r.daily_energy_sold_kwh or 0.0 for r in results]
        achat = [-(r.daily_energy_bought_kwh or 0.0) for r in results]

        x = np.arange(len(months))
        bar_width = 0.38

        fig, ax = plt.subplots(figsize=(11, 5))

        # Production bars (left of each month)
        bars_prod = ax.bar(
            x - bar_width / 2, production, bar_width,
            color='#A8C947', label='Production quotidienne (kWh)'
        )
        # Stacked consumption bars (right of each month): jour + nuit
        bars_day = ax.bar(
            x + bar_width / 2, cons_day, bar_width,
            color='#C5E8E8', label='Consommation de jour (kWh)'
        )
        bars_night = ax.bar(
            x + bar_width / 2, cons_night, bar_width, bottom=cons_day,
            color='#1F6C6C', label='Consommation de nuit (kWh)'
        )

        # Achat as a filled area below zero
        ax.fill_between(
            x, achat, 0,
            color='#F8C9CA', alpha=0.7, label='Achat (kWh)'
        )
        # Bilan line (daily net energy)
        ax.plot(
            x, bilan,
            color='#F39C12', linewidth=2.2, marker='o', markersize=4,
            label='Bilan (kWh)'
        )
        # Revente line (energy sold)
        ax.plot(
            x, revente,
            color='#1F6C6C', linewidth=2.0, marker='o', markersize=4,
            markerfacecolor='white', markeredgewidth=1.5,
            label='Revente (kWh)'
        )

        # Numeric labels above the production bars in black so they don't
        # overlap with the consumption stack labels sitting inside the bars.
        for bar, val in zip(bars_prod, production):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    bar.get_height() + 1.5,
                    f'{val:.2f}',
                    ha='center', va='bottom', fontsize=7, color='#212121',
                )
        # Numeric labels inside the consumption stacks
        for bar, val in zip(bars_day, cons_day):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    bar.get_height() / 2.0,
                    f'{val:.2f}',
                    ha='center', va='center', fontsize=7, color='#1F6C6C'
                )
        for bar, val, base in zip(bars_night, cons_night, cons_day):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    base + val / 2.0,
                    f'{val:.2f}',
                    ha='center', va='center', fontsize=7, color='white'
                )
        # Numeric labels on the Achat area (under the bar group)
        for xi, val in zip(x, achat):
            if val < 0:
                ax.text(
                    xi, val - 2.0,
                    f'{val:.2f}',
                    ha='center', va='top', fontsize=7, color='#B95860'
                )

        # Axes / styling
        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=0, fontsize=8)
        ax.set_ylabel('kWh', fontsize=10)
        ax.axhline(0, color='#9e9e9e', linewidth=0.8)
        ax.grid(axis='y', alpha=0.3)
        for spine in ('top', 'right', 'bottom', 'left'):
            ax.spines[spine].set_visible(False)

        # Legend on top, two rows
        ax.legend(
            loc='upper center', bbox_to_anchor=(0.5, 1.18),
            ncol=3, frameon=False, fontsize=9
        )

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none', transparent=False)
        plt.close()

        return base64.b64encode(buffer.getvalue())

    def _generate_energy_balance_chart(self):
        """Chart 3: annual energy balance tri-layer donut.

        Three concentric layers that all share the same angular
        segmentation [Autoconso, Vente, Achat] so the pieces line up:

        - Outer ring  = Production arc (blue). Left OPEN at the Achat
          angle — the gap visualises the energy the customer had to buy
          instead of produce on site.
        - Middle ring = total energy flow, split into three colours:
          Autoconso (teal), Vente (yellow), Achat (pink). Full circle.
        - Inner disk  = Consommation (black) with the Vente wedge CUT
          OUT (sold energy is not consumed).
        """
        import math
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
        import io
        import base64

        results = self.monthly_result_ids
        if not results:
            return False

        prod_total = (
            self.pvgis_annual_production_kwh
            or self.annual_production_kwh
            or sum(results.mapped('monthly_production_kwh'))
            or 0.0
        )
        conso_total = sum(results.mapped('monthly_consumption_kwh')) or 0.0
        autocons_total = sum(results.mapped('monthly_autoconsumption_kwh')) or 0.0

        # Derive Vente and Achat so the donut is mathematically closed:
        #   Production = Autoconso + Vente   (what we did with our production)
        #   Consommation = Autoconso + Achat (where our consumption came from)
        # Using the raw monthly_energy_sold/bought fields would leave a gap
        # because the model only tracks nighttime grid purchases as "Achat".
        vente_total = max(0.0, prod_total - autocons_total)
        achat_total = max(0.0, conso_total - autocons_total)

        # Common angular reference: total energy flow through the system.
        total_angle_ref = autocons_total + vente_total + achat_total
        if total_angle_ref <= 0:
            return False

        # Colour palette consistent with the Production vs Consommation bar chart.
        color_production = '#A8C947'    # lime green (production bars)
        color_autoconso = '#1F6C6C'     # dark teal (conso nuit / revente line)
        color_vente = '#F39C12'         # orange (bilan line)
        color_achat = '#F8C9CA'         # light pink (achat area)
        color_consommation = '#111111'  # near-black inner disk
        white = '#FFFFFF'
        label_color = '#212121'         # all numeric labels in black

        def _fmt(val):
            return f'{val:,.2f} kWh'

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.set_aspect('equal')

        # All three layers share this segment order so their angles line up.
        segment_values = [autocons_total, vente_total, achat_total]

        # ----- Layer 1: outer Production arc (Autoconso+Vente = Production,
        # Achat angle left as an open gap) -----
        outer_wedges, _ = ax.pie(
            segment_values,
            colors=[color_production, color_production, white],
            radius=1.0,
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.22, edgecolor=white, linewidth=2),
        )
        # Hide the Achat gap edge so it reads as an opening, not a wedge.
        outer_wedges[2].set_linewidth(0)
        outer_wedges[2].set_edgecolor('none')

        # ----- Layer 2: middle breakdown (three colours) -----
        middle_wedges, _ = ax.pie(
            segment_values,
            colors=[color_autoconso, color_vente, color_achat],
            radius=0.76,
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.22, edgecolor=white, linewidth=2),
        )

        # ----- Layer 3: inner Consommation disk (full pie) with Vente
        # wedge cut out (painted white) -----
        inner_wedges, _ = ax.pie(
            segment_values,
            colors=[color_consommation, white, color_consommation],
            radius=0.50,
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.50, edgecolor=white, linewidth=2),
        )
        inner_wedges[1].set_linewidth(0)
        inner_wedges[1].set_edgecolor('none')

        # Helper: place a label at the mid-angle of a wedge.
        def _label_wedge(wedge, value, color, radial_offset=0.08, ha_hint=None):
            angle = (wedge.theta2 + wedge.theta1) / 2.0
            rad = math.radians(angle)
            # Place the label at the mid-radius of the wedge (inside the
            # visible ring) rather than offset from the outer edge.
            mid_r = wedge.r - (wedge.width / 2.0) if hasattr(wedge, 'width') else wedge.r
            r = mid_r + radial_offset
            x = math.cos(rad) * r
            y = math.sin(rad) * r
            ha = ha_hint if ha_hint else ('left' if x >= 0 else 'right')
            ax.text(
                x, y, _fmt(value),
                ha=ha, va='center',
                color=color, fontsize=11, fontweight='bold',
            )

        # Middle-ring value labels — all in black for readability.
        # Each label sits at the centre of its own wedge.
        _label_wedge(middle_wedges[0], autocons_total, label_color, radial_offset=0, ha_hint='center')
        if vente_total > 0:
            _label_wedge(middle_wedges[1], vente_total, label_color, radial_offset=0, ha_hint='center')
        if achat_total > 0:
            _label_wedge(middle_wedges[2], achat_total, label_color, radial_offset=0, ha_hint='center')

        # Production total outside the outer arc, below the donut.
        prod_wedge = outer_wedges[0]
        prod_angle = (prod_wedge.theta2 + prod_wedge.theta1) / 2.0
        prod_rad = math.radians(prod_angle)
        ax.text(
            math.cos(prod_rad) * 1.12, math.sin(prod_rad) * 1.12,
            _fmt(prod_total),
            ha='center', va='center',
            color=label_color, fontsize=12, fontweight='bold',
        )

        # Consommation total inside the black disk — white so it shows
        # against the dark background.
        ax.text(
            0.05, 0, _fmt(conso_total),
            ha='left', va='center',
            color='white', fontsize=11, fontweight='bold', zorder=5,
        )

        # 5-entry legend across the top of the figure.
        legend_handles = [
            Patch(facecolor=color_production, label='Production'),
            Patch(facecolor=color_autoconso, label='Autoconso'),
            Patch(facecolor=color_vente, label='Vente'),
            Patch(facecolor=color_achat, label='Achat'),
            Patch(facecolor=color_consommation, label='Consommation'),
        ]
        ax.legend(
            handles=legend_handles,
            loc='upper center', bbox_to_anchor=(0.5, 1.12),
            ncol=3, frameon=False, fontsize=11,
        )

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
        lat, lng = self._get_lat_lng()
        if not lat or not lng:
            raise UserError(_(
                "Veuillez d'abord renseigner les coordonnées (latitude et longitude).\n"
                "Vous pouvez les obtenir à partir de l'adresse d'installation via un service de géocodage."
            ))
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise UserError(_(
                "Coordonnées GPS invalides (latitude: %s, longitude: %s).\n"
                "La latitude doit être entre -90 et 90, la longitude entre -180 et 180."
            ) % (lat, lng))

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
                latitude=lat,
                longitude=lng
            )

            # Parse the response and match to sale order panels
            parsed_data = solar_api.parse_building_insights(
                api_response,
                target_panels=self.number_of_panels,  # Match panel count to sale order
                target_panel_watts=self.panel_unit_power_wc,  # Scale production to actual panel wattage
                latitude=lat,  # For Data Layers API fallback
                longitude=lng  # For Data Layers API fallback
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
        lat, lng = self._get_lat_lng()
        if not lat or not lng or not self.total_pv_power_wc:
            missing_fields = []
            if not lat:
                missing_fields.append('latitude')
            if not lng:
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
                latitude=lat,
                longitude=lng,
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

        # Cent-precise distribution of the annual consumption default so
        # sum(monthly_consumption_kwh) matches what the user entered.
        consumption_distribution = []
        if self.default_monthly_consumption_kwh:
            annual_total = self.default_monthly_consumption_kwh * 12
            consumption_distribution = self._distribute_annual_consumption(annual_total, 12)

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
            if consumption_distribution:
                month_conso = consumption_distribution[month_num - 1]
                monthly_result_vals.update(self._apply_consumption_ratio(month_conso, days))
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

        # Cent-precise distribution of the annual consumption default so
        # sum(monthly_consumption_kwh) matches what the user entered.
        consumption_distribution = []
        if self.default_monthly_consumption_kwh:
            annual_total = self.default_monthly_consumption_kwh * 12
            consumption_distribution = self._distribute_annual_consumption(annual_total, 12)

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
            if consumption_distribution:
                month_conso = consumption_distribution[month_num - 1]
                monthly_result_vals.update(self._apply_consumption_ratio(month_conso, days))
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
