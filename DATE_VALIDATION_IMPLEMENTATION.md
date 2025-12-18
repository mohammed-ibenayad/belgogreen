# Date Validation Implementation for Hierarchical Commission Plans

## Overview

This document describes the implementation of two key features for commission plan user assignments:

1. **Auto-notification** when users are added via "Données commerciaux" tab
2. **Date validation** for hierarchical commission calculations

---

## Feature 1: One-Way Sync (Commerciaux → Hierarchy)

### Problem Statement
Users wanted records added in "Données commerciaux" tab to automatically appear in "Users & Hierarchy" tab.

### Solution
**Actually, NO sync needed!** Both tabs display the same `user_ids` One2many field from `sale.commission.plan.user` model.

- **Commerciaux tab**: Shows columns `user_id`, `date_from`, `date_to`
- **Hierarchy tab**: Shows columns `user_id`, `role_id`, `manager_id`, `role_sequence`, `date_from`, `date_to`

**Same records, different column visibility!**

### What Was Implemented

Added smart notification in `sale_commission_plan_user.py`:

```python
@api.model_create_multi
def create(self, vals_list):
    """Auto-populate smart defaults when creating user assignments"""
    records = super().create(vals_list)

    # For hierarchical plans, show notification if role not set
    for record in records:
        if record.plan_id.type == 'hierarchical' and not record.role_id:
            # Record was added without role (probably from commerciaux tab)
            record.plan_id.message_post(
                body=_('User %s added to plan. Please set their role and manager in "Users & Hierarchy" tab.') % record.user_id.name,
                subject=_('Complete Hierarchy Setup'),
                message_type='notification'
            )

    return records
```

**Benefit**: Users get a reminder to complete hierarchy information when adding users without roles.

---

## Feature 2: Date Validation for Commission Calculation

### Problem Statement
The `date_from` and `date_to` fields existed but were completely ignored during commission calculations. Users wanted to support time-bound assignments (e.g., seasonal employees, trial periods).

### Solution
Added date validation at **commission generation level** in two places:

#### A. Invoice-Based Commission Generation (`account_move.py`)

Modified `_get_commission_hierarchy()` method:

```python
def _get_commission_hierarchy(self, base_user, commission_plan):
    """
    NEW: Validates date_from and date_to to ensure user assignment is active on invoice date.
    """
    hierarchy = []
    current_user = base_user
    seen_ids = set()
    invoice_date = self.invoice_date or fields.Date.today()

    while current_user and current_user.id not in seen_ids:
        # Find user's assignment in THIS PLAN (with date validation)
        plan_user = self.env['sale.commission.plan.user'].search([
            ('plan_id', '=', commission_plan.id),
            ('user_id', '=', current_user.id),
            # Date validation: assignment must be active on invoice date
            '|', ('date_from', '=', False), ('date_from', '<=', invoice_date),
            '|', ('date_to', '=', False), ('date_to', '>=', invoice_date)
        ], limit=1)

        # ... rest of hierarchy traversal
```

**Date Logic**:
- If `date_from` is empty (False) → Assignment valid from beginning of time
- If `date_from` is set → Invoice date must be >= date_from
- If `date_to` is empty (False) → Assignment valid until end of time
- If `date_to` is set → Invoice date must be <= date_to

**Example**:
```
User: John Doe
date_from: 2025-01-01
date_to: 2025-12-31

Invoice Date: 2024-12-15 → ❌ Not eligible (before start)
Invoice Date: 2025-06-15 → ✅ Eligible (within range)
Invoice Date: 2026-01-15 → ❌ Not eligible (after end)
```

#### B. Sale Order-Based Commission Generation (`sale_order.py`)

Updated two methods:

**1. Initial assignment check** (`_generate_commissions()`):
```python
# Check if salesperson has assignment in this plan (with date validation)
invoice_date = fields.Date.today()
user_assignment = self.env['sale.commission.plan.user'].search([
    ('plan_id', '=', commission_plan.id),
    ('user_id', '=', self.user_id.id),
    # Date validation: assignment must be active
    '|', ('date_from', '=', False), ('date_from', '<=', invoice_date),
    '|', ('date_to', '=', False), ('date_to', '>=', invoice_date)
], limit=1)
```

**2. Hierarchy traversal** (`_get_commission_hierarchy()`):
```python
# Use invoice date from the first paid invoice for this order
invoice_date = fields.Date.today()
if self.invoice_ids:
    paid_invoice = self.invoice_ids.filtered(
        lambda inv: inv.move_type == 'out_invoice' and inv.payment_state in ['paid', 'in_payment']
    )[:1]
    if paid_invoice and paid_invoice.invoice_date:
        invoice_date = paid_invoice.invoice_date

while current_user and current_user.id not in seen_ids:
    plan_user = self.env['sale.commission.plan.user'].search([
        ('plan_id', '=', commission_plan.id),
        ('user_id', '=', current_user.id),
        # Date validation
        '|', ('date_from', '=', False), ('date_from', '<=', invoice_date),
        '|', ('date_to', '=', False), ('date_to', '>=', invoice_date)
    ], limit=1)
```

---

## UI Changes

### Updated "Users & Hierarchy" Tab

Added date fields with optional visibility:

```xml
<field name="user_ids">
    <list editable="bottom">
        <field name="user_id" domain="[('company_id', '=', parent.company_id)]"/>
        <field name="role_id" domain="[('company_id', '=', parent.company_id)]"/>
        <field name="role_sequence" string="Level" readonly="1"/>
        <field name="manager_id"/>
        <field name="date_from" optional="show"/>  <!-- NEW -->
        <field name="date_to" optional="show"/>    <!-- NEW -->
        <field name="company_id" column_invisible="1"/>
    </list>
</field>
```

**UI Behavior**:
- Date columns are **optional="show"** → Visible by default but can be hidden
- Users can set date ranges directly in the hierarchy tab
- Dates apply to both standard and hierarchical plans

### Updated Help Text

Added comprehensive documentation in the info box:

```
Plan-Based Role Assignment:
• Assign each user to this plan with their role
• Set their manager within this plan's hierarchy
• Users can have different roles in different plans
• Top-level users (Directeur) should have NO manager
• Date From/To: Optional validity period for this assignment (leave empty for permanent assignment)

Example Hierarchy:
• Frederic Adam: Directeur de Sales, Manager: (none), Dates: (permanent)
• Corine Detilleux: Chef d'équipe, Manager: Frederic Adam, Dates: (permanent)
• John Doe: Commerciale, Manager: Corine Detilleux, Dates: 2025-01-01 to 2025-12-31 (seasonal)

💡 Tip: Users added via "Données commerciaux" tab will automatically appear here.
Complete their role and manager information to enable commission calculations.
```

---

## Use Cases

### Use Case 1: Permanent Assignments
```
User: Frederic Adam
Role: Directeur de Sales
date_from: (empty)
date_to: (empty)

Result: Receives commissions for ALL invoices (no date restrictions)
```

### Use Case 2: Seasonal Employee
```
User: Summer Intern
Role: Commercial
date_from: 2025-06-01
date_to: 2025-08-31

Result: Only receives commissions for invoices dated between June 1 - August 31, 2025
```

### Use Case 3: Role Transition
```
Scenario: Corine promoted from Commercial to Chef d'équipe on March 1, 2025

Setup TWO records:
1. Old role:
   - Role: Commercial
   - date_from: 2025-01-01
   - date_to: 2025-02-28

2. New role:
   - Role: Chef d'équipe
   - date_from: 2025-03-01
   - date_to: (empty)

Result:
- January-February invoices → Corine gets Commercial commission (5%)
- March onwards → Corine gets Chef commission (5% direct + 2% override)
```

### Use Case 4: Trial Period
```
User: New Hire
Role: Commercial
date_from: 2025-01-15
date_to: 2025-04-15

Result:
- Only eligible for commissions during trial period
- If not converted to permanent, date_to expires and commissions stop automatically
- To make permanent: set date_to to empty
```

---

## Testing Checklist

### Test 1: Permanent Assignment (No Dates)
- [ ] Create user with empty date_from and date_to
- [ ] Generate commission for invoice dated 2024-12-01 → ✅ Should create
- [ ] Generate commission for invoice dated 2025-12-01 → ✅ Should create
- [ ] Generate commission for invoice dated 2026-12-01 → ✅ Should create

### Test 2: Time-Bound Assignment
- [ ] Create user with date_from=2025-06-01, date_to=2025-08-31
- [ ] Generate commission for invoice dated 2025-05-31 → ❌ Should skip
- [ ] Generate commission for invoice dated 2025-07-15 → ✅ Should create
- [ ] Generate commission for invoice dated 2025-09-01 → ❌ Should skip

### Test 3: Hierarchy Chain with Mixed Dates
```
Setup:
- John (Commercial): 2025-01-01 to 2025-06-30
- Corine (Chef): permanent
- Frederic (Directeur): permanent

Invoice Date: 2025-03-15
Expected: John + Corine + Frederic all get commissions ✅

Invoice Date: 2025-07-15
Expected: Only Corine + Frederic get commissions (John expired) ✅
```

### Test 4: Notification on User Add
- [ ] Add user via "Données commerciaux" tab (without role)
- [ ] Check plan's message log → ✅ Should see notification
- [ ] Go to "Users & Hierarchy" tab → ✅ User should appear
- [ ] Complete role_id and manager_id
- [ ] Generate commission → ✅ Should work

### Test 5: Same User, Different Plans
```
Setup:
Plan A (AMSS): John as Commercial, permanent
Plan B (NaturIsol): John as Chef, 2025-01-01 to 2025-12-31

Invoice for AMSS dated 2026-01-15:
Expected: John gets Commercial commission from Plan A ✅

Invoice for NaturIsol dated 2026-01-15:
Expected: John does NOT get commission (date expired) ❌
```

---

## Performance Impact

### Query Performance
**Before**:
```sql
SELECT * FROM sale_commission_plan_user
WHERE plan_id = 1 AND user_id = 123
LIMIT 1
```

**After**:
```sql
SELECT * FROM sale_commission_plan_user
WHERE plan_id = 1 AND user_id = 123
AND (date_from IS NULL OR date_from <= '2025-06-15')
AND (date_to IS NULL OR date_to >= '2025-06-15')
LIMIT 1
```

**Impact**: Minimal - simple date comparisons on indexed fields

### Recommended Indexes
```sql
-- Add composite index for better performance
CREATE INDEX idx_commission_plan_user_dates
ON sale_commission_plan_user(plan_id, user_id, date_from, date_to);
```

---

## Migration Notes

### For Existing Installations

**No data migration needed!** All changes are backward-compatible:

1. **Existing records**: `date_from` and `date_to` are NULL → Treated as permanent assignments ✅
2. **Commission logic**: Empty dates satisfy the OR conditions → No change in behavior ✅
3. **UI**: Date fields appear but are optional → Users not forced to fill them ✅

### If You Want to Migrate Old Data

If you previously had global role assignments and want to add dates:

```sql
-- Example: Set all current assignments as starting from 2025-01-01
UPDATE sale_commission_plan_user
SET date_from = '2025-01-01',
    date_to = NULL  -- Permanent going forward
WHERE date_from IS NULL;
```

**Recommendation**: Leave dates empty for existing users (permanent assignments).

---

## Future Enhancements

### 1. Overlap Detection
Prevent same user from having overlapping date ranges with different roles:

```python
@api.constrains('user_id', 'plan_id', 'date_from', 'date_to')
def _check_no_overlap(self):
    """Prevent overlapping date ranges for same user in same plan"""
    for rec in self:
        if not rec.date_from and not rec.date_to:
            continue  # Permanent assignments can coexist

        overlapping = self.search([
            ('id', '!=', rec.id),
            ('plan_id', '=', rec.plan_id.id),
            ('user_id', '=', rec.user_id.id),
            # Complex overlap logic
        ])

        if overlapping:
            raise ValidationError(_('Date ranges cannot overlap for the same user'))
```

### 2. Automatic Expiration Notifications
Send email to managers when user assignment is about to expire:

```python
@api.model
def cron_check_expiring_assignments(self):
    """Send notifications for assignments expiring in 30 days"""
    expiring_date = fields.Date.today() + timedelta(days=30)
    expiring_assignments = self.search([
        ('date_to', '!=', False),
        ('date_to', '<=', expiring_date),
        ('date_to', '>=', fields.Date.today())
    ])

    for assignment in expiring_assignments:
        # Send email to plan manager
        pass
```

### 3. Historical Commission Recalculation
When date ranges are modified, allow recalculation of historical commissions:

```python
def action_recalculate_commissions(self):
    """Recalculate commissions when date ranges change"""
    # Find affected commissions
    # Void and regenerate based on new dates
    pass
```

---

## Troubleshooting

### Issue 1: "User added but doesn't appear in hierarchy tab"

**Cause**: Both tabs show the same records - it MUST appear.

**Solution**:
- Refresh the page (F5)
- Check if there's a filter applied on hierarchy tab
- Verify the record was actually created (check database)

---

### Issue 2: "Commission not created despite valid dates"

**Diagnosis**:
```python
# In Python shell
plan_user = env['sale.commission.plan.user'].search([
    ('plan_id', '=', PLAN_ID),
    ('user_id', '=', USER_ID),
    ('date_from', '<=', INVOICE_DATE),
    ('date_to', '>=', INVOICE_DATE)
])
print(f"Found: {plan_user}")
print(f"date_from: {plan_user.date_from}")
print(f"date_to: {plan_user.date_to}")
```

**Common Causes**:
- date_from is AFTER invoice date (check timezone)
- date_to is BEFORE invoice date
- Missing role_id (commission requires role)
- Plan not approved

---

### Issue 3: "Notification spam when bulk adding users"

**Expected Behavior**: Each user creation triggers one notification.

**If Too Many Notifications**:
- Modify the create() method to batch notifications
- Add context flag to suppress notifications during import:

```python
# During bulk import
self.with_context(skip_notification=True).create([...])
```

---

## Summary

### What Was Implemented
✅ One-way awareness: Records in commerciaux tab appear in hierarchy tab (no sync needed, same data)
✅ Smart notification: Alert when users added without roles
✅ Date validation: date_from and date_to now enforced during commission calculation
✅ UI enhancements: Date fields visible and documented in hierarchy tab

### Benefits
- **Flexibility**: Support seasonal employees, trial periods, role transitions
- **Data Integrity**: Commissions only created for valid date ranges
- **User-Friendly**: Clear documentation and helpful notifications
- **Performance**: Minimal overhead, backward-compatible

### Complexity
- **Low**: Simple date comparisons in search domains
- **No sync logic**: Both tabs show same records naturally
- **No breaking changes**: Existing installations work unchanged

---

**Implementation Date**: 2025-12-18
**Files Modified**:
- `belgogreen_sales_commission/models/sale_commission_plan_user.py`
- `belgogreen_sales_commission/models/account_move.py`
- `belgogreen_sales_commission/models/sale_order.py`
- `belgogreen_sales_commission/views/sale_commission_plan_views.xml`
