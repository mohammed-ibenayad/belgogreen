# -*- coding: utf-8 -*-

import requests
import logging
import json
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SolarApiClient(models.AbstractModel):
    """Google Solar API Client"""
    _name = 'solar.api.client'
    _description = 'Google Solar API Client'

    SOLAR_API_BASE_URL = 'https://solar.googleapis.com/v1'

    @api.model
    def _get_api_key(self):
        """Get Google Solar API key from system parameters"""
        api_key = self.env['ir.config_parameter'].sudo().get_param('google_solar_api_key')
        if not api_key:
            raise UserError(_(
                "Google Solar API key not configured.\n"
                "Please configure it in Settings > Technical > Parameters > System Parameters\n"
                "Key: 'google_solar_api_key'"
            ))
        return api_key

    @api.model
    def get_data_layers(self, latitude=None, longitude=None, radius_meters=50):
        """
        Get data layers (imagery) from Google Solar API

        This is a fallback method when Building Insights API doesn't provide rgbUrl.
        The Data Layers API specifically provides GeoTIFF imagery layers.

        Args:
            latitude: Building latitude
            longitude: Building longitude
            radius_meters: Radius in meters around the location (default 50m)

        Returns:
            dict: API response containing imagery URLs (rgbUrl, dsmUrl, etc.)

        Raises:
            UserError: If API call fails
        """
        api_key = self._get_api_key()
        url = f"{self.SOLAR_API_BASE_URL}/dataLayers:get"

        # Build query parameters
        params = {
            'key': api_key,
            'radiusMeters': radius_meters,
            'requiredQuality': 'MEDIUM',
        }

        if latitude is not None and longitude is not None:
            params['location.latitude'] = latitude
            params['location.longitude'] = longitude
        else:
            raise UserError(_("Latitude and longitude must be provided"))

        try:
            _logger.info(f"📸 Calling Google Solar Data Layers API for location: {latitude}, {longitude}")

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Log what we received
            _logger.info(f"✅ Data Layers Response received. Keys: {list(data.keys())}")
            if 'rgbUrl' in data:
                _logger.info(f"✅ RGB imagery URL found in Data Layers")
            else:
                _logger.warning(f"❌ No rgbUrl in Data Layers - imagery not available")

            return data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise UserError(_(
                    "No imagery available for this location.\n"
                    "The Google Solar API may not have coverage in this area."
                ))
            elif e.response.status_code == 403:
                raise UserError(_(
                    "Google Solar API access forbidden.\n"
                    "Please check your API key and ensure the Solar API is enabled."
                ))
            else:
                _logger.error(f"Data Layers API HTTP error: {e}")
                raise UserError(_(
                    "Failed to fetch imagery data: %s\n"
                    "Status code: %s"
                ) % (str(e), e.response.status_code))

        except requests.exceptions.RequestException as e:
            _logger.error(f"Data Layers API request error: {e}")
            raise UserError(_(
                "Failed to connect to Google Solar Data Layers API: %s\n"
                "Please check your internet connection."
            ) % str(e))

        except Exception as e:
            _logger.error(f"Unexpected error calling Data Layers API: {e}")
            raise UserError(_("Unexpected error: %s") % str(e))

    @api.model
    def get_building_insights(self, latitude=None, longitude=None):
        """
        Get building insights from Google Solar API

        Args:
            latitude: Building latitude
            longitude: Building longitude

        Returns:
            dict: API response containing solar potential, imagery URLs, etc.

        Raises:
            UserError: If API call fails
        """
        api_key = self._get_api_key()
        url = f"{self.SOLAR_API_BASE_URL}/buildingInsights:findClosest"

        # Build query parameters
        params = {'key': api_key}

        if latitude is not None and longitude is not None:
            params['location.latitude'] = latitude
            params['location.longitude'] = longitude
        else:
            raise UserError(_("Latitude and longitude must be provided"))

        # Request MEDIUM quality imagery for better availability
        params['requiredQuality'] = 'MEDIUM'

        try:
            _logger.info(f"☀️ Calling Google Solar API for location: {latitude}, {longitude}")

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Log what we received
            _logger.info(f"✅ API Response received. Keys: {list(data.keys())}")
            if 'solarPotential' in data:
                sp = data['solarPotential']
                _logger.info(f"Solar Potential keys: {list(sp.keys())}")

                # Check for imagery
                if 'rgbUrl' in sp:
                    _logger.info(f"✅ RGB imagery URL found")
                else:
                    _logger.warning(f"❌ No rgbUrl - imagery not available for this location")

                if 'solarPanelConfigs' in sp:
                    _logger.info(f"Found {len(sp['solarPanelConfigs'])} panel configurations")

            return data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise UserError(_(
                    "No solar data available for this location.\n"
                    "The Google Solar API may not have coverage in this area."
                ))
            elif e.response.status_code == 403:
                raise UserError(_(
                    "Google Solar API access forbidden.\n"
                    "Please check your API key and ensure the Solar API is enabled."
                ))
            else:
                _logger.error(f"Solar API HTTP error: {e}")
                raise UserError(_(
                    "Failed to fetch solar data: %s\n"
                    "Status code: %s"
                ) % (str(e), e.response.status_code))

        except requests.exceptions.RequestException as e:
            _logger.error(f"Solar API request error: {e}")
            raise UserError(_(
                "Failed to connect to Google Solar API: %s\n"
                "Please check your internet connection."
            ) % str(e))

        except Exception as e:
            _logger.error(f"Unexpected error calling Solar API: {e}")
            raise UserError(_("Unexpected error: %s") % str(e))

    @api.model
    def download_imagery(self, imagery_url):
        """
        Download imagery from URL and convert to viewable format

        Args:
            imagery_url: URL to satellite imagery

        Returns:
            bytes: Image data in PNG format (viewable in browsers)
        """
        if not imagery_url:
            return None

        try:
            # GeoTIFF URLs from Data Layers API need API key appended
            # Check if URL already has parameters
            if 'geoTiff:get' in imagery_url and 'key=' not in imagery_url:
                api_key = self._get_api_key()
                separator = '&' if '?' in imagery_url else '?'
                imagery_url = f"{imagery_url}{separator}key={api_key}"
                _logger.info(f"📸 Downloading GeoTIFF with API key authentication")

            _logger.info(f"📸 Downloading imagery from: {imagery_url[:100]}...")
            response = requests.get(imagery_url, timeout=30)
            response.raise_for_status()
            _logger.info(f"✅ Downloaded {len(response.content)} bytes")

            # Convert GeoTIFF to PNG for browser display
            if 'geoTiff:get' in imagery_url:
                _logger.info(f"🔄 Converting GeoTIFF to PNG for display...")
                converted_image = self._convert_geotiff_to_png(response.content)
                if converted_image:
                    _logger.info(f"✅ Converted to PNG: {len(converted_image)} bytes")
                    return converted_image
                else:
                    _logger.warning(
                        "⚠️ GeoTIFF conversion failed - skipping image. "
                        "Install rasterio (pip install rasterio) for GeoTIFF support."
                    )
                    return None

            return response.content

        except Exception as e:
            _logger.error(f"Failed to download imagery: {e}")
            return None

    @api.model
    def _convert_geotiff_to_png(self, geotiff_data):
        """
        Convert GeoTIFF data to PNG format for browser display

        Args:
            geotiff_data: Raw GeoTIFF bytes

        Returns:
            bytes: PNG image data, or None if conversion fails
        """
        try:
            import io
            import numpy as np
            from PIL import Image

            # Try rasterio first (proper GeoTIFF library)
            try:
                import rasterio
                from rasterio.io import MemoryFile

                _logger.info(f"📖 Reading GeoTIFF with rasterio...")

                # Open GeoTIFF from memory
                with MemoryFile(geotiff_data) as memfile:
                    with memfile.open() as dataset:
                        # Read RGB bands (bands 1, 2, 3)
                        # GeoTIFF from Google Solar API typically has RGB data
                        bands = dataset.count
                        _logger.info(f"📊 GeoTIFF has {bands} bands")

                        if bands >= 3:
                            # Read RGB bands
                            red = dataset.read(1)
                            green = dataset.read(2)
                            blue = dataset.read(3)

                            # Stack into RGB array
                            rgb = np.dstack((red, green, blue))
                        elif bands == 1:
                            # Grayscale - duplicate to RGB
                            gray = dataset.read(1)
                            rgb = np.dstack((gray, gray, gray))
                        else:
                            _logger.error(f"Unexpected number of bands: {bands}")
                            return None

                        # Normalize to 0-255 if needed
                        if rgb.max() > 255:
                            rgb = ((rgb - rgb.min()) / (rgb.max() - rgb.min()) * 255).astype(np.uint8)
                        else:
                            rgb = rgb.astype(np.uint8)

                        # Convert to PIL Image
                        img = Image.fromarray(rgb, mode='RGB')

                        _logger.info(f"📐 Image size: {img.size[0]}x{img.size[1]} pixels")

                        # Save as PNG
                        png_buffer = io.BytesIO()
                        img.save(png_buffer, format='PNG', optimize=True)
                        return png_buffer.getvalue()

            except ImportError:
                _logger.warning("rasterio not available - trying PIL fallback")
                # Fall through to PIL-only method

            # Fallback: Try PIL directly (works for some TIFF files)
            _logger.info(f"📖 Reading TIFF with PIL...")
            tiff_buffer = io.BytesIO(geotiff_data)
            img = Image.open(tiff_buffer)

            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            _logger.info(f"📐 Image size: {img.size[0]}x{img.size[1]} pixels")

            # Save as PNG
            png_buffer = io.BytesIO()
            img.save(png_buffer, format='PNG', optimize=True)
            return png_buffer.getvalue()

        except ImportError as e:
            _logger.error(f"Required libraries not installed: {e}")
            _logger.error("Install with: pip install Pillow rasterio")
            return None
        except Exception as e:
            _logger.error(f"Failed to convert GeoTIFF to PNG: {e}")
            _logger.error(f"Error type: {type(e).__name__}")
            return None

    @api.model
    def parse_building_insights(self, api_response, target_panels=None, target_panel_watts=None, latitude=None, longitude=None):
        """
        Parse building insights API response into usable data

        Args:
            api_response: dict from get_building_insights()
            target_panels: Number of panels in sale order (to match closest config)
            target_panel_watts: Actual panel wattage (API assumes 400W, so we scale)
            latitude: Location latitude (for Data Layers API fallback)
            longitude: Location longitude (for Data Layers API fallback)

        Returns:
            dict with parsed data:
                - imagery_url: URL to RGB satellite image
                - imagery_data: Downloaded image bytes
                - roof_area_m2: Total roof area
                - max_panels_count: Maximum number of panels the roof can accommodate
                - yearly_energy_kwh: Annual energy production estimate (scaled to actual panel watts)
                - monthly_energy_kwh: List of 12 monthly values (scaled to actual panel watts)
        """
        result = {
            'imagery_url': None,
            'imagery_data': None,
            'roof_area_m2': None,
            'max_panels_count': None,
            'yearly_energy_kwh': None,
            'monthly_energy_kwh': [],
        }

        if not api_response:
            return result

        # Extract solar potential data
        solar_potential = api_response.get('solarPotential', {})

        # Try to get imagery URL from Building Insights response
        if 'rgbUrl' in solar_potential:
            result['imagery_url'] = solar_potential['rgbUrl']
            _logger.info(f"✅ Found imagery URL in Building Insights: {result['imagery_url'][:100]}...")
            # Download the imagery
            result['imagery_data'] = self.download_imagery(result['imagery_url'])
        else:
            # Fallback: Try Data Layers API to get imagery
            _logger.info(f"⚠️ No rgbUrl in Building Insights - trying Data Layers API fallback")
            if latitude and longitude:
                try:
                    data_layers = self.get_data_layers(latitude=latitude, longitude=longitude)
                    if 'rgbUrl' in data_layers:
                        result['imagery_url'] = data_layers['rgbUrl']
                        _logger.info(f"✅ Found imagery URL in Data Layers: {result['imagery_url'][:100]}...")
                        # Download the imagery
                        result['imagery_data'] = self.download_imagery(result['imagery_url'])
                except Exception as e:
                    _logger.warning(f"⚠️ Data Layers API fallback failed: {e}")
            else:
                _logger.warning(f"⚠️ Cannot use Data Layers fallback - no lat/lon provided")

        # Get roof area
        if 'wholeRoofStats' in solar_potential:
            roof_stats = solar_potential['wholeRoofStats']
            if 'areaMeters2' in roof_stats:
                result['roof_area_m2'] = roof_stats['areaMeters2']
                _logger.info(f"📏 Roof area extracted: {result['roof_area_m2']:.2f} m² (from wholeRoofStats.areaMeters2)")

        # Get maximum panel count
        if 'maxArrayPanelsCount' in solar_potential:
            result['max_panels_count'] = solar_potential['maxArrayPanelsCount']
            _logger.info(f"🔢 Max panels capacity: {result['max_panels_count']} panels (from maxArrayPanelsCount)")

        # Also log other area fields for comparison
        if 'buildingStats' in solar_potential:
            building_area = solar_potential['buildingStats'].get('areaMeters2')
            if building_area:
                _logger.info(f"📐 Building footprint: {building_area:.2f} m² (from buildingStats.areaMeters2)")

        if 'maxArrayAreaMeters2' in solar_potential:
            max_array = solar_potential['maxArrayAreaMeters2']
            _logger.info(f"☀️ Max array area: {max_array:.2f} m² (from maxArrayAreaMeters2)")

        # Get panel configurations and find the best match
        if 'solarPanelConfigs' in solar_potential:
            configs = solar_potential['solarPanelConfigs']
            _logger.info(f"Found {len(configs)} solar panel configurations")

            if target_panels and target_panels > 0:
                # Find the configuration closest to the target number of panels
                best_config = min(
                    configs,
                    key=lambda c: abs(c.get('panelsCount', 0) - target_panels)
                )
                _logger.info(f"🎯 Matching to sale order: {target_panels} panels")
                _logger.info(f"✅ Best match: {best_config.get('panelsCount')} panels, "
                           f"{best_config.get('yearlyEnergyDcKwh', 0):.0f} kWh/year")
            else:
                # Use the last (largest) configuration as default
                # Google Solar API returns configs sorted ascending by panelsCount
                best_config = configs[-1]
                _logger.info(f"Using default config (max): {best_config.get('panelsCount')} panels")

            # Get production values (API assumes 400W panels)
            api_yearly_kwh = best_config.get('yearlyEnergyDcKwh', 0)
            api_monthly_kwh = best_config.get('monthlyEnergyDcKwh', [])

            # Scale production to actual panel wattage
            # Google Solar API uses 400W as default panel capacity
            API_DEFAULT_PANEL_WATTS = 400
            scaling_factor = 1.0

            if target_panel_watts and target_panel_watts > 0:
                scaling_factor = target_panel_watts / API_DEFAULT_PANEL_WATTS
                _logger.info(f"⚡ Panel wattage scaling: {API_DEFAULT_PANEL_WATTS}W (API) → {target_panel_watts}W (actual)")
                _logger.info(f"📈 Scaling factor: {scaling_factor:.4f} ({scaling_factor*100:.2f}%)")
                _logger.info(f"📊 API production (400W): {api_yearly_kwh:.0f} kWh/year")
                _logger.info(f"✅ Scaled production ({target_panel_watts}W): {api_yearly_kwh * scaling_factor:.0f} kWh/year")
            else:
                _logger.warning(f"⚠️ No panel wattage specified - using API's 400W default")

            # Apply scaling
            result['yearly_energy_kwh'] = api_yearly_kwh * scaling_factor

            # Scale monthly values if available
            if api_monthly_kwh:
                result['monthly_energy_kwh'] = [month_kwh * scaling_factor for month_kwh in api_monthly_kwh]
                _logger.info(f"📊 Monthly production data: {len(result['monthly_energy_kwh'])} months (scaled)")

        return result

    @api.model
    def get_pvgis_monthly(self, latitude, longitude, peakpower_kw, angle=None, aspect=None):
        """
        Get monthly production data from PVGIS API

        Args:
            latitude: Location latitude
            longitude: Location longitude
            peakpower_kw: Peak power in kW (not Wc!)
            angle: Panel tilt/inclination in degrees (optional)
            aspect: Azimuth orientation in degrees (optional, 0=South)

        Returns:
            dict with:
                - monthly_kwh: List of 12 monthly energy values
                - yearly_kwh: Total yearly energy
                - pvgis_info: Metadata about the calculation
        """
        PVGIS_API_URL = 'https://re.jrc.ec.europa.eu/api/v5_3/PVcalc'

        # Build parameters
        params = {
            'lat': latitude,
            'lon': longitude,
            'peakpower': peakpower_kw,
            'loss': 14,  # Default system losses (%)
            'pvtechchoice': 'crystSi',
            'mountingplace': 'building',
            'outputformat': 'json'
        }

        # Add optional parameters
        if angle is not None:
            params['angle'] = angle
        if aspect is not None:
            params['aspect'] = aspect

        try:
            _logger.info(f"☀️ Calling PVGIS API for location: {latitude}, {longitude}")
            _logger.info(f"⚡ System: {peakpower_kw} kW, angle={angle}°, aspect={aspect}°")

            response = requests.get(PVGIS_API_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract monthly data
            monthly_data = data.get('outputs', {}).get('monthly', {}).get('fixed', [])

            if not monthly_data:
                _logger.warning("⚠️ No monthly data in PVGIS response")
                return None

            # Extract E_m (monthly energy) for each month
            monthly_kwh = [month['E_m'] for month in monthly_data if 'E_m' in month]

            # Get yearly total
            totals = data.get('outputs', {}).get('totals', {}).get('fixed', {})
            yearly_kwh = totals.get('E_y', sum(monthly_kwh))

            _logger.info(f"✅ PVGIS returned {len(monthly_kwh)} monthly values")
            _logger.info(f"📊 PVGIS yearly total: {yearly_kwh:.0f} kWh")
            _logger.info(f"📅 Monthly breakdown: {[f'{m:.0f}' for m in monthly_kwh]}")

            return {
                'monthly_kwh': monthly_kwh,
                'yearly_kwh': yearly_kwh,
                'pvgis_info': {
                    'location': f"{latitude}, {longitude}",
                    'peakpower_kw': peakpower_kw,
                    'system_loss': 14,
                    'technology': 'crystSi'
                }
            }

        except requests.exceptions.HTTPError as e:
            _logger.error(f"PVGIS API HTTP error: {e}")
            return None

        except requests.exceptions.RequestException as e:
            _logger.error(f"PVGIS API request error: {e}")
            return None

        except Exception as e:
            _logger.error(f"Unexpected error calling PVGIS API: {e}")
            return None
