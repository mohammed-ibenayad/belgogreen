# Commission Status Refactoring Plan

## Overview
Simplify commission tracking by replacing dual status fields (`state` + `payment_status`) with a single unified `status` field.

**Date:** 2025-12-22

---

## Goals

### ✅ What We're Doing
- **Merge** `state` and `payment_status` into single `status` field on `sale.commission` model
- **Remove** draft status - commissions start as "unpaid" when created
- **Keep** claim progress bar unchanged (draft → pending → approved → rejected)
- **Simplify** user experience with clear, linear payment flow

### ❌ What We're NOT Changing
- Claim model status flow (stays the same)
- Claim progress bar/workflow
- Purchase order workflow
- Payment processing logic

---

## New Commission Status Flow

```
┌─────────────┐
│   UNPAID    │ ← Commission created (invoice paid), ready to claim
└─────────────┘
      ↓ (user claims)
┌─────────────┐
│   CLAIMED   │ ← Included in claim (pending manager approval)
└─────────────┘
      ↓ (manager approves claim)
┌─────────────┐
│  APPROVED   │ ← Claim approved, PO created
└─────────────┘
      ↓ (PO confirmed)
┌─────────────┐
│ PROCESSING  │ ← Waiting for vendor bill and payment
└─────────────┘
      ↓ (bill paid)
┌─────────────┐
│    PAID     │ ← Payment processed ✅
└─────────────┘

      (from any state)
         ↓
┌─────────────┐
│ CANCELLED   │ ← Commission cancelled
└─────────────┘
```

**Progress Bar:** `unpaid → claimed → approved → processing → paid`

---

## Implementation Steps

### **Step 1: Update Commission Model** (`models/sale_commission.py`)

#### 1.1 Remove Old Fields
```python
# DELETE these fields:
- state (line 173-177)
- payment_status (line 118-124)
```

#### 1.2 Add New Unified Status Field
```python
# ADD after line 117:
status = fields.Selection([
    ('unpaid', 'Unpaid'),
    ('claimed', 'Claimed'),
    ('approved', 'Approved'),
    ('processing', 'Processing'),
    ('paid', 'Paid'),
    ('cancelled', 'Cancelled')
], string='Status', default='unpaid', required=True, tracking=True,
   help='unpaid: Ready to claim | claimed: In claim | approved: Claim approved | '
        'processing: Awaiting payment | paid: Payment received')
```

#### 1.3 Update Computed Field `_compute_can_be_paid` (line 220-235)
```python
# CHANGE:
- commission.payment_status in ['unpaid', 'claimed', 'processing']
- commission.state == 'confirmed'

# TO:
- commission.status in ['unpaid', 'claimed', 'processing']
```

#### 1.4 Update Methods

**action_confirm (line 246-248):**
```python
# DELETE this method entirely - commissions start as 'unpaid'
# OR change to just validate, not change status
```

**action_cancel (line 250-255):**
```python
# CHANGE:
def action_cancel(self):
    """Cancel commission"""
    self.write({'status': 'cancelled'})
```

**action_claim_payment (line 257-273):**
```python
# CHANGE line 260:
- if self.payment_status == 'unpaid':
# TO:
+ if self.status == 'unpaid':
```

**action_create_payment (line 299-315):**
```python
# No change needed (uses can_be_paid computed field)
```

---

### **Step 2: Update Claim Model** (`models/sale_commission_claim.py`)

#### 2.1 Update action_submit (line 275-288)
```python
# CHANGE line 284:
- self.commission_ids.write({'payment_status': 'claimed'})
# TO:
+ self.commission_ids.write({'status': 'claimed'})
```

#### 2.2 Update action_reject (line 342-361)
```python
# CHANGE line 358:
- claim.commission_ids.write({'payment_status': 'unpaid'})
# TO:
+ claim.commission_ids.write({'status': 'unpaid'})
```

#### 2.3 Update Commission Domain in Form View
The domain for selecting commissions in claims needs updating (we'll do this in views)

---

### **Step 3: Update Purchase Order Model** (`models/purchase_order.py`)

Find where commissions are set to 'processing' when PO is confirmed:

```python
# CHANGE:
- commissions.write({'payment_status': 'processing'})
# TO:
+ commissions.write({'status': 'processing'})
```

---

### **Step 4: Update Account Move Model** (`models/account_move.py`)

Find the `_mark_commissions_paid()` method:

```python
# CHANGE:
- commissions.write({'payment_status': 'paid', ...})
# TO:
+ commissions.write({'status': 'paid', ...})
```

---

### **Step 5: Update Commission Views** (`views/sale_commission_views.xml`)

#### 5.1 Update Tree View (line 10-30)
```xml
<!-- CHANGE line 11-13 decorations: -->
<list string="Commissions"
      decoration-success="status == 'paid'"
      decoration-warning="status == 'claimed'"
      decoration-muted="status == 'cancelled'"
      ...>

    <!-- CHANGE line 27-28: -->
    <field name="status" string="Status" width="90px"/>
    <!-- DELETE: -->
    <field name="state" string="State" optional="hide" width="80px"/>
</list>
```

#### 5.2 Update Form View (line 38-101)

**Header section (line 39-51):**
```xml
<!-- DELETE confirm/cancel buttons (line 40-41) -->

<!-- UPDATE button conditions: -->
<button name="action_claim_payment" string="Claim Payment" type="object" class="oe_highlight"
        invisible="status != 'unpaid' or user_id != uid"
        groups="belgogreen_sales_commission.group_commission_user"/>

<button name="action_view_claim" string="View Claim" type="object" class="oe_highlight"
        invisible="status != 'claimed' or claim_count == 0 or user_id != uid"
        groups="belgogreen_sales_commission.group_commission_user"/>

<!-- DELETE line 51 (state statusbar) -->
<!-- ADD new statusbar: -->
<field name="status" widget="statusbar"
       statusbar_visible="unpaid,claimed,approved,processing,paid"/>
```

**Payment Status group (line 86-90):**
```xml
<!-- CHANGE group name to "Status": -->
<group string="Status">
    <field name="status" readonly="1"/>
    <field name="payment_date" readonly="1"/>
    <field name="payment_id" readonly="1"/>
</group>
```

**Percentage override field (line 80):**
```xml
<!-- CHANGE condition: -->
<field name="percentage_override"
       groups="belgogreen_sales_commission.group_commission_manager"
       readonly="status in ['processing', 'paid']"/>
```

#### 5.3 Update Search View (line 109-147)

```xml
<!-- DELETE lines 128-129 (Draft/Confirmed filters) -->

<!-- UPDATE filters (line 118-121): -->
<filter string="Unpaid" name="unpaid" domain="[('status', '=', 'unpaid')]"/>
<filter string="Claimed" name="claimed" domain="[('status', '=', 'claimed')]"/>
<filter string="Approved" name="approved" domain="[('status', '=', 'approved')]"/>
<filter string="Processing" name="processing" domain="[('status', '=', 'processing')]"/>
<filter string="Paid" name="paid" domain="[('status', '=', 'paid')]"/>

<!-- UPDATE grouping (line 141): -->
<filter string="Status" name="group_status" context="{'group_by': 'status'}"/>
<!-- DELETE: -->
<filter string="Payment Status" name="group_payment_status" .../>
```

#### 5.4 Update Kanban View (line 181-216)

```xml
<!-- CHANGE line 187: -->
<field name="status"/>

<!-- CHANGE line 197: -->
t-attf-class="#{record.status.raw_value == 'paid' ? 'badge-success' :
               record.status.raw_value == 'claimed' ? 'badge-warning' :
               'badge-secondary'}">
    <field name="status"/>
</span>
```

---

### **Step 6: Update Claim Views** (`views/sale_commission_claim_views.xml`)

#### 6.1 Update Commission Selection Domain (line 84)
```xml
<!-- CHANGE line 84: -->
domain="[('user_id', '=', user_id),
         ('status', '=', 'unpaid'),
         ('can_be_paid', '=', True)]">
```

#### 6.2 Update Commission List in Claim Form (line 85)
```xml
<!-- CHANGE line 85: -->
<list decoration-success="status == 'paid'"
      create="false"
      delete="1">
    ...
    <!-- CHANGE line 95: -->
    <field name="status" string="Status" width="90px"/>
</list>
```

---

### **Step 7: Update Invoice/Order Creation Logic**

Find where commissions are created (likely in `models/account_move.py` or `models/sale_order.py`):

```python
# When creating commissions, they should start with status='unpaid'
# ENSURE default value is set:
{
    'status': 'unpaid',  # NOT 'draft'
    # ... other fields
}
```

---

### **Step 8: Update Dashboard/Reports** (if any)

Check these files:
- `models/commission_dashboard.py`
- `static/src/js/commission_dashboard.js`
- Any report templates

**Update references:**
```javascript
// CHANGE:
- payment_status
- state
// TO:
+ status
```

---

### **Step 9: Update Security/Access Rules**

Check `security/ir.model.access.csv` and any record rules - no field name changes needed, but verify logic.

---

### **Step 10: Update Translations** (`i18n/fr.po`)

Find and update all translations for:
- "Draft" → remove
- "Confirmed" → remove
- "Payment Status" → "Statut"
- Add translations for new statuses

---

## Testing Checklist

### Scenario 1: New Commission Creation
- [ ] Invoice paid → commission created with status='unpaid'
- [ ] Commission appears in "My Commissions" as unpaid
- [ ] "Claim Payment" button visible

### Scenario 2: Claiming
- [ ] User clicks "Claim Payment"
- [ ] Claim created in draft
- [ ] User adds commissions (only unpaid shown in selection)
- [ ] User submits claim
- [ ] Commission status → 'claimed'
- [ ] "View Claim" button visible on commission

### Scenario 3: Approval
- [ ] Manager approves claim
- [ ] PO created
- [ ] Commission status → 'approved'

### Scenario 4: Processing
- [ ] Manager confirms PO
- [ ] Email sent to contractor
- [ ] Commission status → 'processing'

### Scenario 5: Payment
- [ ] Vendor bill created and paid
- [ ] Commission status → 'paid'
- [ ] Status shown as green/success in lists

### Scenario 6: Rejection
- [ ] Manager rejects claim
- [ ] Commission status → 'unpaid'
- [ ] User can claim again

### Scenario 7: Cancellation
- [ ] Manager cancels commission
- [ ] Status → 'cancelled'
- [ ] Cannot be claimed

### Scenario 8: Progress Bar
- [ ] Commission form shows: unpaid → claimed → approved → processing → paid
- [ ] Current status highlighted
- [ ] All statuses visible in bar

### Scenario 9: Filtering
- [ ] Search filters work for all statuses
- [ ] Grouping by status works
- [ ] Decorations (colors) display correctly

### Scenario 10: Permissions
- [ ] Users can only claim their own unpaid commissions
- [ ] Managers can see all commission statuses
- [ ] Status updates restricted appropriately

---

## Migration Considerations

### For Existing Data

**Option A: Data Migration Script** (Recommended)
```python
# Create a migration script to convert existing records:
def migrate_commission_status():
    commissions = env['sale.commission'].search([])
    for comm in commissions:
        # Map old values to new status
        if comm.payment_status == 'paid':
            new_status = 'paid'
        elif comm.payment_status == 'processing':
            new_status = 'processing'
        elif comm.payment_status == 'claimed':
            new_status = 'claimed'
        elif comm.payment_status == 'cancelled' or comm.state == 'cancelled':
            new_status = 'cancelled'
        elif comm.state == 'confirmed' and comm.payment_status == 'unpaid':
            new_status = 'unpaid'
        elif comm.state == 'draft':
            new_status = 'unpaid'  # Convert drafts to unpaid
        else:
            new_status = 'unpaid'  # Default fallback

        comm.write({'status': new_status})
```

**Option B: SQL Direct Update** (Faster)
```sql
-- Add new column
ALTER TABLE sale_commission ADD COLUMN status VARCHAR;

-- Migrate data with priority: payment_status > state
UPDATE sale_commission
SET status = CASE
    WHEN payment_status = 'paid' THEN 'paid'
    WHEN payment_status = 'processing' THEN 'processing'
    WHEN payment_status = 'claimed' THEN 'claimed'
    WHEN payment_status = 'cancelled' OR state = 'cancelled' THEN 'cancelled'
    WHEN state = 'confirmed' AND payment_status = 'unpaid' THEN 'unpaid'
    WHEN state = 'draft' THEN 'unpaid'
    ELSE 'unpaid'
END;

-- Drop old columns (after verification)
-- ALTER TABLE sale_commission DROP COLUMN state;
-- ALTER TABLE sale_commission DROP COLUMN payment_status;
```

---

## Rollback Plan

If issues occur:

1. **Keep backup** of database before migration
2. **Keep old fields** for 1-2 weeks (rename to `state_old`, `payment_status_old`)
3. **Add computed field** to sync back if needed:
   ```python
   state_old = fields.Selection([...], compute='_compute_old_state')

   def _compute_old_state(self):
       for rec in self:
           if rec.status in ['paid', 'processing', 'claimed', 'unpaid']:
               rec.state_old = 'confirmed'
           else:
               rec.state_old = 'draft'
   ```

---

## Communication Plan

### To Users (Contractors/Sales)
> **"Commission tracking simplified!"**
>
> We've streamlined how you track your commissions. Instead of seeing both "State" and "Payment Status", you now see one clear status showing exactly where your commission is in the payment process:
>
> - **Unpaid** - Ready for you to claim
> - **Claimed** - You've submitted a claim (pending approval)
> - **Approved** - Your claim was approved
> - **Processing** - Payment is being processed
> - **Paid** - You've been paid! ✅
>
> Everything works the same way - we've just made it clearer!

### To Managers
> **"Commission status tracking updated"**
>
> We've merged the "State" and "Payment Status" fields into a single "Status" field for clarity:
> - Commissions no longer have a "draft" status - they're created as "unpaid"
> - The status bar now shows the complete payment journey
> - All existing logic remains the same (approval, PO creation, payment processing)
> - Claims keep their existing workflow (draft → pending → approved)

### To Accounting
> **"Commission status field consolidated"**
>
> Technical change: `state` + `payment_status` → single `status` field
> - Same workflow (PO → Bill → Payment)
> - Status automatically updates to 'paid' when bill is paid
> - No changes to your process

---

## Files to Modify

### Models (7 files)
1. ✅ `models/sale_commission.py` - Main changes
2. ✅ `models/sale_commission_claim.py` - Update write() calls
3. ✅ `models/purchase_order.py` - Update status on PO confirm
4. ✅ `models/account_move.py` - Update status on payment
5. ✅ `models/commission_dashboard.py` - Update references
6. ⚠️ Check `models/sale_order.py` - Commission creation
7. ⚠️ Check `models/res_users.py` - Any status checks

### Views (2 files)
1. ✅ `views/sale_commission_views.xml` - Major updates
2. ✅ `views/sale_commission_claim_views.xml` - Domain updates

### JavaScript (1 file)
1. ⚠️ `static/src/js/commission_dashboard.js` - Update field references

### Data (1 file)
1. ⚠️ `i18n/fr.po` - Update translations

### Documentation (2 files)
1. ✅ `PAYMENT_REFACTOR_SUMMARY.md` - Update to reflect changes
2. ✅ Create `COMMISSION_STATUS_REFACTOR_PLAN.md` - This document

---

## Success Criteria

- ✅ Single `status` field replaces `state` and `payment_status`
- ✅ No "draft" status - commissions start as "unpaid"
- ✅ Progress bar shows clear payment journey
- ✅ All existing workflows continue to function
- ✅ No data loss during migration
- ✅ All tests pass
- ✅ Users report clearer understanding of commission status

---

## Timeline Estimate

- **Analysis & Planning**: ✅ Complete
- **Model Changes**: 2-3 hours
- **View Updates**: 2-3 hours
- **Testing**: 3-4 hours
- **Data Migration**: 1 hour
- **Documentation**: 1 hour
- **Total**: ~10-12 hours

---

## Questions to Resolve Before Starting

1. ✅ **Confirmed:** Remove draft status, start with unpaid
2. ✅ **Confirmed:** Keep claim workflow as-is
3. ❓ **Pending:** Should "approved" status exist on commissions, or jump from "claimed" to "processing"?
   - Current plan: Yes, keep "approved" (matches claim approval)
4. ❓ **Pending:** What happens to commissions when claim is rejected - back to "unpaid"?
   - Current code: Yes (line 358)
5. ❓ **Pending:** Can users edit/cancel claimed commissions, or are they locked?
   - Recommend: Locked once claimed (can cancel entire claim in draft)

---

**Status:** 📋 Ready for Review
**Next Step:** Get approval, then proceed with implementation
**Created:** 2025-12-22
