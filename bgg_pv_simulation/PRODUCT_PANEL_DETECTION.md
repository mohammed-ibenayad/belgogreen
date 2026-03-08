# Product-Based Panel Detection

**Date:** 2026-01-03
**Feature:** Automatic panel detection from sale order products

## Overview

The PV simulation module now automatically detects solar panels from the sale order line items. Panel specifications are stored on products and automatically calculated when creating a simulation.

---

## How It Works

### 1. Product Configuration

Products can be marked as solar panels with specific power ratings:

**New fields on `product.template`:**
- `is_solar_panel` (Boolean) - Checkbox to identify solar panel products
- `panel_unit_power_wc` (Float) - Power output per panel in Wc

### 2. Automatic Detection

When a PV simulation is linked to a sale order, the system:

1. Scans all sale order line items
2. Filters products where `is_solar_panel = True`
3. Sums quantities to get total number of panels
4. Reads unit power from the product specification
5. Calculates total PV power: `number_of_panels × panel_unit_power_wc`

### 3. Computed Fields

The following fields in `pv.simulation` are now **automatically computed**:
- `number_of_panels` - Total quantity from sale order
- `panel_unit_power_wc` - From product specification
- `total_pv_power_wc` - Calculated total power

All three fields are **read-only** and update automatically when sale order changes.

---

## Configuration Steps

### Step 1: Set Up Solar Panel Products

1. Go to **Sales → Products → Products**
2. Create or edit a product
3. Check the **"Is Solar Panel"** checkbox
4. Enter the **"Panel Unit Power (Wc)"** (e.g., 400 for a 400W panel)
5. Save the product

### Step 2: Create Sale Order with Panels

1. Create a new sale order
2. Add solar panel products to order lines
3. Set quantities (e.g., 20 panels)
4. Add other products (inverters, batteries, etc.) - these won't count as panels

### Step 3: Create PV Simulation

1. Open the sale order
2. Click **"PV Simulation"** button
3. The simulation will automatically show:
   - Number of panels: 20
   - Panel unit power: 400 Wc (from product)
   - Total PV power: 8,000 Wc (calculated)

---

## Sample Products Included

The module includes 4 sample solar panel products:

| Product Code | Name | Power | Price | Type |
|--------------|------|-------|-------|------|
| PANEL-400W | High Performance 400W | 400 Wc | €350 | Monocrystalline |
| PANEL-350W | Standard 350W | 350 Wc | €280 | Polycrystalline |
| PANEL-300W | Budget 300W | 300 Wc | €220 | Polycrystalline |
| PANEL-450W-BF | Premium Bifacial 450W | 450 Wc | €450 | Bifacial Mono |

Plus a non-panel product for testing:
- **INV-5KW**: Solar Inverter 5kW (€1,200) - Won't be counted as panels

---

## Technical Details

### Model: `product.template`

**File:** `models/product_template.py`

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_solar_panel = fields.Boolean(
        string='Is Solar Panel',
        default=False,
        help='Check this if the product is a solar panel'
    )
    panel_unit_power_wc = fields.Float(
        string='Panel Unit Power (Wc)',
        help='Power output per panel in Wc (Watts-crête)'
    )
```

### Model: `pv.simulation`

**File:** `models/pv_simulation.py`

**Compute Method:**
```python
@api.depends('sale_order_id', 'sale_order_id.order_line',
             'sale_order_id.order_line.product_id',
             'sale_order_id.order_line.product_id.is_solar_panel',
             'sale_order_id.order_line.product_id.panel_unit_power_wc',
             'sale_order_id.order_line.product_uom_qty')
def _compute_panel_data(self):
    """Calculate panel data from sale order line items"""
    # Filter panel products
    panel_lines = sale_order.order_line.filtered(
        lambda l: l.product_id.is_solar_panel
    )

    # Sum quantities
    number_of_panels = sum(line.product_uom_qty for line in panel_lines)

    # Get unit power from first panel product
    panel_unit_power_wc = panel_lines[0].product_id.panel_unit_power_wc

    # Calculate total
    total_pv_power_wc = number_of_panels × panel_unit_power_wc
```

---

## View Updates

### Product Form View

**File:** `views/product_template_views.xml`

Added fields to product form:
- Checkbox "Is Solar Panel" in general section
- "Panel Unit Power" field (visible only when is_solar_panel = True)

### PV Simulation Form View

**File:** `views/pv_simulation_views.xml`

Updated "Panel Configuration" section:
- Changed title to "Panel Configuration (Auto-detected from Sale Order)"
- Made all three panel fields **readonly**
- Fields automatically populate from sale order

---

## Data Files

### Sample Products

**File:** `data/product_solar_panel_data.xml`

Contains 5 sample products:
- 4 solar panels with different specs
- 1 inverter (non-panel) for testing

All products are created with `noupdate="1"` to avoid overwriting customizations.

---

## Benefits

### ✅ Automatic Data Entry
- No manual entry of panel count or power
- Data comes from actual products being sold
- Eliminates data entry errors

### ✅ Product Catalog Integration
- Panel specifications managed in product catalog
- Consistent data across quotations
- Easy to maintain and update

### ✅ Accurate Quotations
- Panel data matches what's actually being sold
- Total power reflects actual products
- Simulations tied to real quotation items

### ✅ Flexible Product Mix
- Can mix different panel types in one order
- System uses first panel's unit power
- Non-panel products automatically excluded

---

## Important Notes

### Multiple Panel Types

If a sale order contains multiple types of panels with **different power ratings**, the system currently:
- Uses the **first panel's unit power** for calculations
- Sums **all panel quantities**

**Example:**
- 10× 400W panels
- 5× 350W panels
- System shows: 15 panels × 400W = 6,000W

**Recommendation:** Use panels of the same power rating in one quotation for accurate calculations.

**Future Enhancement:** Could calculate weighted average or total power directly.

### Manual Override

Currently, there is **no manual override**. Panel data is always computed from sale order.

If you need manual entry:
1. Create a generic "Custom Solar Panel" product
2. Set the desired unit power on the product
3. Adjust quantity on the sale order line

### Retroactive Updates

The panel fields update automatically when:
- Sale order lines are added/removed
- Product quantities change
- Product specifications change

No need to regenerate simulations - data updates in real-time.

---

## Migration Notes

### Existing Simulations

Old simulations created before this feature:
- Will show **0 panels** and **0 power**
- Need to have products marked as solar panels in their sale orders
- Need to regenerate simulation to recalculate

### Upgrading

When upgrading the module:
1. Existing products won't have `is_solar_panel` set
2. You'll need to mark your panel products manually
3. Set `panel_unit_power_wc` on each panel product
4. Existing simulations will recalculate automatically

---

## Testing Checklist

- [ ] Create a product and mark as solar panel
- [ ] Set panel unit power on the product
- [ ] Create a sale order with panel products
- [ ] Add panels with different quantities
- [ ] Add non-panel products (should be ignored)
- [ ] Create PV simulation from sale order
- [ ] Verify panel count matches quantity
- [ ] Verify unit power matches product
- [ ] Verify total power is correct
- [ ] Change sale order quantity
- [ ] Verify simulation updates automatically
- [ ] Test with multiple panel types
- [ ] Test with no panels in sale order

---

## Troubleshooting

### Problem: Panel fields show 0

**Cause:** No products marked as solar panels in sale order

**Solution:**
1. Check sale order has line items
2. Verify products have `is_solar_panel = True`
3. Check `panel_unit_power_wc` is set on products

### Problem: Wrong panel count

**Cause:** Non-panel products marked incorrectly

**Solution:**
1. Check which products have `is_solar_panel = True`
2. Uncheck flag on non-panel products
3. Simulation will recalculate

### Problem: Unit power is 0

**Cause:** Product's `panel_unit_power_wc` field is empty

**Solution:**
1. Open the product
2. Set the "Panel Unit Power (Wc)" field
3. Simulation will update automatically

---

## Future Enhancements

### Possible Improvements

1. **Multi-panel power calculation**
   - Calculate total power from all panel types
   - Don't assume same unit power
   - Show breakdown by panel type

2. **Panel product category**
   - Use product category instead of boolean flag
   - Filter by "Solar Panels" category
   - Better organization

3. **Manual override option**
   - Allow manual entry if needed
   - Checkbox to override automatic detection
   - Useful for custom installations

4. **Panel specifications**
   - Store more panel data (efficiency, dimensions)
   - Show in simulation
   - Use in calculations

5. **Validation warnings**
   - Warn if multiple panel types
   - Alert if no panels detected
   - Show panel type mismatch

---

## API Changes

### Affected Models

**Modified:**
- `pv.simulation` - Panel fields now computed
- Added: `product.template` - New solar panel fields

### Backwards Compatibility

⚠️ **Breaking Change:**
- `number_of_panels` changed from manual to computed
- `panel_unit_power_wc` changed from manual to computed
- Old data will reset to 0 unless products are configured

### Migration Required

If upgrading from previous version:
1. Mark existing panel products with `is_solar_panel`
2. Set `panel_unit_power_wc` on products
3. Simulations will auto-recalculate

---

## Files Modified/Created

### New Files
- `models/product_template.py` - Product extension
- `views/product_template_views.xml` - Product form updates
- `data/product_solar_panel_data.xml` - Sample products

### Modified Files
- `models/__init__.py` - Import product_template
- `models/pv_simulation.py` - Compute method for panel data
- `views/pv_simulation_views.xml` - Readonly panel fields
- `__manifest__.py` - Added new view and data files

---

**Implementation Complete:** 2026-01-03
**Developer:** Claude Code Agent
**Branch:** claude/review-solar-specs-gap-4Kh5c
