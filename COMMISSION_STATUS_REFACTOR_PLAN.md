# Commission Status Refactoring Plan

**Date:** 2025-12-22
**Status:** Development - Not yet in production

---

## Goal

Simplify commission tracking by replacing dual status fields (`state` + `payment_status`) with a single unified `status` field.

### Changes:
- ✅ Merge `state` and `payment_status` → single `status` field
- ✅ Remove "draft" status - commissions start as "unpaid"
- ✅ Keep claim workflow unchanged

### New Status Flow:
```
unpaid → claimed → approved → processing → paid
                                  ↓
                              cancelled (from any state)
```

---

## Implementation Changes

### 1. **models/sale_commission.py**

#### Replace fields (lines 118-124, 173-177):
```python
# DELETE:
payment_status = fields.Selection([...])  # line 118-124
state = fields.Selection([...])           # line 173-177

# ADD (after line 117):
status = fields.Selection([
    ('unpaid', 'Unpaid'),
    ('claimed', 'Claimed'),
    ('approved', 'Approved'),
    ('processing', 'Processing'),
    ('paid', 'Paid'),
    ('cancelled', 'Cancelled')
], string='Status', default='unpaid', required=True, tracking=True)
```

#### Update `_compute_can_be_paid()` (line 220-235):
```python
# CHANGE:
commission.payment_status in ['unpaid', 'claimed', 'processing'] and
commission.state == 'confirmed'

# TO:
commission.status in ['unpaid', 'claimed', 'processing']
```

#### Update methods:
```python
# DELETE action_confirm() entirely (line 246-248)

# UPDATE action_cancel() (line 250-255):
def action_cancel(self):
    self.write({'status': 'cancelled'})

# UPDATE action_claim_payment() (line 260):
if self.status == 'unpaid':
```

---

### 2. **models/sale_commission_claim.py**

```python
# UPDATE action_submit() (line 284):
self.commission_ids.write({'status': 'claimed'})

# UPDATE action_reject() (line 358):
claim.commission_ids.write({'status': 'unpaid'})
```

---

### 3. **models/purchase_order.py**

Search for where commissions are set to 'processing' on PO confirmation:
```python
# CHANGE:
commissions.write({'payment_status': 'processing'})
# TO:
commissions.write({'status': 'processing'})
```

---

### 4. **models/account_move.py**

In `_mark_commissions_paid()` method:
```python
# CHANGE:
commissions.write({'payment_status': 'paid', ...})
# TO:
commissions.write({'status': 'paid', ...})
```

---

### 5. **views/sale_commission_views.xml**

#### Tree view (line 10-30):
```xml
<!-- UPDATE decorations: -->
decoration-success="status == 'paid'"
decoration-warning="status == 'claimed'"
decoration-muted="status == 'cancelled'"

<!-- CHANGE field: -->
<field name="status" string="Status" width="90px"/>

<!-- DELETE state field -->
```

#### Form view:
```xml
<!-- Header (line 39-51) -->
<!-- DELETE action_confirm and action_cancel buttons -->

<!-- UPDATE button conditions: -->
invisible="status != 'unpaid' or user_id != uid"  <!-- for claim payment -->
invisible="status != 'claimed' or claim_count == 0"  <!-- for view claim -->

<!-- REPLACE statusbar: -->
<field name="status" widget="statusbar"
       statusbar_visible="unpaid,claimed,approved,processing,paid"/>

<!-- Payment group (line 86-90) -->
<group string="Status">
    <field name="status" readonly="1"/>
    ...
</group>

<!-- Percentage override (line 80) -->
readonly="status in ['processing', 'paid']"
```

#### Search view (line 109-147):
```xml
<!-- DELETE Draft/Confirmed filters -->

<!-- UPDATE filters: -->
<filter string="Unpaid" name="unpaid" domain="[('status', '=', 'unpaid')]"/>
<filter string="Claimed" name="claimed" domain="[('status', '=', 'claimed')]"/>
<filter string="Approved" name="approved" domain="[('status', '=', 'approved')]"/>
<filter string="Processing" name="processing" domain="[('status', '=', 'processing')]"/>
<filter string="Paid" name="paid" domain="[('status', '=', 'paid')]"/>

<!-- UPDATE grouping: -->
<filter string="Status" name="group_status" context="{'group_by': 'status'}"/>
```

#### Kanban view (line 181-216):
```xml
<field name="status"/>

<!-- UPDATE badge class: -->
t-attf-class="#{record.status.raw_value == 'paid' ? 'badge-success' :
               record.status.raw_value == 'claimed' ? 'badge-warning' :
               'badge-secondary'}">
    <field name="status"/>
</span>
```

---

### 6. **views/sale_commission_claim_views.xml**

#### Commission selection domain (line 84):
```xml
domain="[('user_id', '=', user_id), ('status', '=', 'unpaid'), ('can_be_paid', '=', True)]"
```

#### Commission list (line 85-96):
```xml
<list decoration-success="status == 'paid'" ...>
    ...
    <field name="status" string="Status" width="90px"/>
</list>
```

---

### 7. **Other files to check**

Search these files for references to `payment_status` or commission `state`:

```bash
grep -r "payment_status" belgogreen_sales_commission/
grep -r "\.state" belgogreen_sales_commission/models/sale_commission*.py
```

Update any found references:
- `models/commission_dashboard.py`
- `static/src/js/commission_dashboard.js`
- Any report templates
- `i18n/fr.po` (translations)

---

## Testing Checklist

1. **Commission Creation**
   - [ ] Invoice paid → commission created with status='unpaid'

2. **Claiming**
   - [ ] User can claim unpaid commissions
   - [ ] Status changes to 'claimed' when claim submitted

3. **Approval**
   - [ ] Status changes to 'approved' when manager approves

4. **Processing**
   - [ ] Status changes to 'processing' when PO confirmed

5. **Payment**
   - [ ] Status changes to 'paid' when vendor bill paid

6. **Rejection**
   - [ ] Status reverts to 'unpaid' when claim rejected

7. **Cancellation**
   - [ ] Status changes to 'cancelled' when commission cancelled

8. **UI**
   - [ ] Progress bar shows correct statuses
   - [ ] Filters work for all statuses
   - [ ] Colors/decorations display correctly
   - [ ] Buttons show/hide based on status

---

## Summary

**Files to modify:**
1. `models/sale_commission.py` - Replace fields, update methods
2. `models/sale_commission_claim.py` - Update status writes
3. `models/purchase_order.py` - Update status on PO confirm
4. `models/account_move.py` - Update status on payment
5. `views/sale_commission_views.xml` - Update all view references
6. `views/sale_commission_claim_views.xml` - Update domain and fields
7. Check JS, dashboard, translations for any other references

**Key changes:**
- Single `status` field instead of `state` + `payment_status`
- No "draft" status - start with "unpaid"
- Clear linear flow: unpaid → claimed → approved → processing → paid

**Ready to implement!**
