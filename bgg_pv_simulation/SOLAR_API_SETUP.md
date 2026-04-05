# Google Solar API Integration - Setup Guide

## Overview

The PV Simulation module now includes integration with **Google Solar API** to automatically:
- 🖼️ **Fetch satellite imagery** of the installation location
- ⚡ **Estimate annual energy production** based on location, roof characteristics, and solar potential
- 📊 **Generate monthly production profiles** from API data
- 🏗️ **Validate roof area** against API-detected building dimensions

## Features

### 1. Automatic Building Imagery
- Fetches high-resolution satellite imagery from Google Solar API
- Automatically populated into `location_image` field
- No more manual uploads needed!

### 2. Production Estimates
- Annual energy production (kWh) based on:
  - Geographic location (lat/lon)
  - Roof area and orientation
  - Historical solar data
- Monthly production breakdown (12 months)
- Auto-creates production profile from API data

### 3. Smart Caching
- API responses cached for **90 days**
- Reduces API costs and improves performance
- Cache is address-based (same address = same cache)
- Manual cache clearing available for admins

### 4. Fallback Support
- Manual entry still works if API fails
- API data supplements but doesn't override user input
- Warnings logged if user input differs significantly from API

---

## Setup Instructions

### Step 1: Get Google Cloud API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing project
3. Enable the **Solar API**:
   - Navigate to **APIs & Services > Library**
   - Search for "Solar API"
   - Click **Enable**
4. Create API credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > API Key**
   - Copy your API key
5. (Optional but recommended) Restrict your API key:
   - Click on your API key to edit
   - Under **API restrictions**, select "Restrict key"
   - Select only "Solar API"
   - Under **Application restrictions**, configure as needed

### Step 2: Configure API Key in Odoo

1. Log in to Odoo as **Administrator**
2. Go to **Settings > Technical > Parameters > System Parameters**
3. Find or create parameter:
   - **Key**: `google_api_key`
   - **Value**: *Your API key from Step 1*
4. Save

That's it! The module will now use this API key automatically.

---

## How to Use

### Fetching Solar Data

1. **Create or open a PV Simulation**
2. **Enter installation address** (required for caching)
3. **Enter latitude and longitude** (required for API call)
   - You can use Google Maps to get these coordinates
   - Right-click on map location > Copy coordinates
4. Click **"🌞 Fetch Solar Data (API)"** button in header
5. Wait for success notification
6. Check updated fields:
   - Location Image (satellite view)
   - Annual Production (if empty)
   - Production Profile (auto-created)
   - Roof Surface (if empty)

### What Gets Updated?

The API fetch will:

✅ **Always Update**:
- Location image (satellite imagery)

✅ **Update if Empty**:
- Roof surface area (m²)
- Annual production (kWh)
- Production profile (monthly percentages)

⚠️ **Log Warnings if Different**:
- If your entered roof area differs from API by >10%
- If your entered production differs from API by >20%

This ensures you maintain control while benefiting from API automation.

---

## API Data Details

### Building Insights Endpoint

The module uses `buildingInsights:findClosest` which provides:

```json
{
  "solarPotential": {
    "maxArrayPanelsCount": 20,
    "maxArrayAreaMeters2": 35.5,
    "wholeRoofStats": {
      "areaMeters2": 50.2
    },
    "solarPanelConfigs": [{
      "panelsCount": 20,
      "yearlyEnergyDcKwh": 5200,
      "monthlyEnergyDcKwh": [420, 480, 550, ...]
    }],
    "rgbUrl": "https://solar.googleapis.com/v1/geoTiff:get?id=..."
  }
}
```

### Cache Structure

Cached data includes:
- API response (full JSON)
- Imagery URL
- Downloaded imagery data
- Yearly production estimate
- Cache expiration (90 days)

---

## Troubleshooting

### Error: "API key not configured"
**Solution**: Follow Step 2 above to configure the API key

### Error: "No solar data available for this location"
**Cause**: Google Solar API doesn't have coverage in this area yet
**Solution**: Use manual entry for now. Coverage is expanding regularly.

### Error: "Access forbidden (403)"
**Possible causes**:
1. API key is incorrect
2. Solar API not enabled in Google Cloud Console
3. API key restrictions blocking the request

**Solution**: Verify Step 1 configuration

### Error: "Please provide latitude and longitude"
**Solution**: Enter coordinates in the Location section before fetching

### API costs too high?
**Tips**:
1. ✅ Cache is enabled by default (90-day retention)
2. ✅ Same address = cached response (no extra API call)
3. ✅ Use "Clear Solar Cache" only when data is outdated
4. Consider setting up billing alerts in Google Cloud Console

---

## API Pricing (as of 2026)

- **Google Solar API**: ~$0.02 per request
- **Free tier**: Check Google Cloud for current free quota
- **Caching saves**: Repeat requests for same address = $0

### Cost Example:
- 100 unique addresses/month = ~$2
- With caching, subsequent views = $0
- Cache valid for 90 days

---

## Advanced Features

### Manual Cache Clearing

**Who**: System administrators only
**When**: Data outdated or incorrect
**How**: Click "Clear Solar Cache" button in simulation form

### Production Profile Auto-Creation

When API returns monthly data:
- Creates profile named: `API Profile - [Simulation Name]`
- Calculates monthly percentages from absolute values
- Automatically assigns to simulation
- Reuses profile if fetching again

### Roof Area Validation

The system compares:
- **User Input**: What you entered manually
- **API Data**: What Google Solar detected

If difference > 10%, a warning is logged for review.

---

## Technical Details

### New Models

1. **`solar.api.cache`**: Stores cached API responses
   - Fields: address_hash, api_response, imagery_url, imagery_data, expires_at
   - Auto-cleanup of expired entries

2. **`solar.api.client`**: Abstract model with API methods
   - `get_building_insights()`: Fetch from API
   - `parse_building_insights()`: Parse response
   - `download_imagery()`: Get satellite image

### New Methods in pv.simulation

- `action_fetch_solar_data()`: Button action to fetch
- `_apply_solar_api_data()`: Apply API data to fields
- `action_clear_solar_cache()`: Admin-only cache clear

### Modified Models

- `pv.simulation`: Added Solar API integration methods
- New fields used: `latitude`, `longitude`, `location_image`

---

## Files Modified

```
models/
├── solar_api_client.py          ← NEW: API client and cache
├── pv_simulation.py             ← Modified: Added API methods
└── __init__.py                  ← Modified: Import solar_api_client

views/
└── pv_simulation_views.xml      ← Modified: Added fetch button

data/
└── solar_api_config.xml         ← NEW: API key config

security/
└── ir.model.access.csv          ← Modified: Cache access rules

__manifest__.py                  ← Modified: Added dependencies
```

---

## Support & Resources

- **Google Solar API Docs**: https://developers.google.com/maps/documentation/solar
- **API Key Management**: https://console.cloud.google.com/apis/credentials
- **Coverage Map**: Check Google Solar API documentation for available regions

---

## Migration Notes

### Upgrading from Previous Version

1. Module upgrade will create `solar.api.cache` model automatically
2. API key configuration is optional (manual entry still works)
3. Existing simulations are not affected
4. New button appears only for saved simulations (`invisible="not id"`)

### Data Privacy

- API requests include: latitude, longitude, address
- No personal customer data sent to Google
- Cached data stored in your Odoo database
- Cache can be cleared anytime by admins

---

## Future Enhancements

Potential additions:
- 🔄 Auto-geocoding from address (lat/lon detection)
- 🌍 Coverage check before API call
- 📊 Data Layers integration (detailed solar flux maps)
- 🔌 Batch processing for multiple simulations
- 📈 API usage tracking and cost monitoring

---

**Questions?** Check the logs for detailed error messages:
```
Settings > Technical > Logging
Filter by: solar.api.client or pv.simulation
```
