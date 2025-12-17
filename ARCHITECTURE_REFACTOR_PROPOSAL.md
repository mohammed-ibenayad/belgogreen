# Commission System Architecture Refactor Proposal

## 🎯 Goal
Move role and hierarchy assignment from **user level** (global) to **plan level** (per-plan), allowing users to have different roles in different commission plans.

---

## 📊 Current Architecture (Problems)

### Current Structure
```python
# res.users (GLOBAL - one role for all plans)
class ResUsers(models.Model):
    commission_role_id = fields.Many2one('sale.commission.role')  # ❌ SINGLE ROLE
    commission_manager_id = fields.Many2one('res.users')  # ❌ SINGLE MANAGER
```

### Problems
1. ❌ **Frederic Adam can't be Directeur for both AMSS and NaturIsol**
2. ❌ Users locked to ONE role across ALL plans
3. ❌ Hierarchy is global, not plan-specific
4. ❌ Can't have different organizational structures per company/plan

---

## ✨ Proposed Architecture (Solution)

### New Structure
```python
# sale.commission.plan.user (PER-PLAN - multiple roles possible)
class SaleCommissionPlanUser(models.Model):
    _name = 'sale.commission.plan.user'
    _description = 'Commission Plan User Assignment'

    plan_id = fields.Many2one('sale.commission.plan', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', required=True)
    role_id = fields.Many2one('sale.commission.role', required=True)
    manager_id = fields.Many2one('res.users', string='Manager in this Plan')

    # Constraints
    _sql_constraints = [
        ('unique_user_plan', 'unique(plan_id, user_id)',
         'A user can only be assigned once per plan!')
    ]

# sale.commission.plan (UPDATED)
class SaleCommissionPlan(models.Model):
    _inherit = 'sale.commission.plan'

    user_ids = fields.One2many('sale.commission.plan.user', 'plan_id')
```

### Benefits
1. ✅ **Frederic can be Directeur in AMSS plan AND Directeur in NaturIsol plan**
2. ✅ Users can have different roles in different plans
3. ✅ Hierarchy is plan-specific
4. ✅ More flexible organizational structures
5. ✅ Better multi-company support

---

## 🔧 Required Changes

### 1. Create New Model: `sale.commission.plan.user`

**File:** `belgogreen_sales_commission/models/sale_commission_plan_user.py`

```python
# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleCommissionPlanUser(models.Model):
    _name = 'sale.commission.plan.user'
    _description = 'Commission Plan User Assignment'
    _order = 'plan_id, role_sequence, user_id'

    # Core fields
    plan_id = fields.Many2one(
        'sale.commission.plan',
        string='Commission Plan',
        required=True,
        ondelete='cascade',
        index=True
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True
    )

    role_id = fields.Many2one(
        'sale.commission.role',
        string='Role',
        required=True,
        domain="[('company_id', '=', company_id)]"
    )

    manager_id = fields.Many2one(
        'res.users',
        string='Manager (in this plan)',
        domain="[('id', '!=', user_id), ('id', 'in', plan_user_ids)]",
        help='Direct manager in THIS commission plan\'s hierarchy'
    )

    # Related/Computed fields
    company_id = fields.Many2one(
        'res.company',
        related='plan_id.company_id',
        store=True,
        readonly=True
    )

    role_sequence = fields.Integer(
        related='role_id.sequence',
        store=True,
        readonly=True
    )

    plan_user_ids = fields.Many2many(
        'res.users',
        compute='_compute_plan_users',
        help='All users in this plan (for manager domain)'
    )

    # SQL constraints
    _sql_constraints = [
        ('unique_user_plan', 'unique(plan_id, user_id)',
         'A user can only be assigned once per commission plan!')
    ]

    @api.depends('plan_id', 'plan_id.user_ids')
    def _compute_plan_users(self):
        """Get all users in the plan for manager selection"""
        for rec in self:
            rec.plan_user_ids = rec.plan_id.user_ids.mapped('user_id')

    @api.constrains('manager_id', 'user_id')
    def _check_no_self_management(self):
        """User cannot be their own manager"""
        for rec in self:
            if rec.manager_id and rec.manager_id.id == rec.user_id.id:
                raise ValidationError(_('A user cannot be their own manager!'))

    @api.constrains('manager_id', 'role_id')
    def _check_manager_hierarchy(self):
        """Manager must have higher hierarchy level (higher sequence)"""
        for rec in self:
            if rec.manager_id:
                # Find manager's role in same plan
                manager_plan_user = self.search([
                    ('plan_id', '=', rec.plan_id.id),
                    ('user_id', '=', rec.manager_id.id)
                ], limit=1)

                if manager_plan_user and manager_plan_user.role_id:
                    if manager_plan_user.role_sequence <= rec.role_sequence:
                        raise ValidationError(_(
                            'Manager %s (level %d - %s) must have higher hierarchy level '
                            'than subordinate %s (level %d - %s).'
                        ) % (
                            rec.manager_id.name, manager_plan_user.role_sequence,
                            manager_plan_user.role_id.name,
                            rec.user_id.name, rec.role_sequence, rec.role_id.name
                        ))

    def name_get(self):
        """Custom display name"""
        result = []
        for rec in self:
            name = '%s - %s (%s)' % (rec.plan_id.name, rec.user_id.name, rec.role_id.name)
            result.append((rec.id, name))
        return result
```

---

### 2. Update `sale.commission.plan` Model

**File:** `belgogreen_sales_commission/models/sale_commission_plan.py`

Add to existing model:
```python
class SaleCommissionPlan(models.Model):
    _inherit = 'sale.commission.plan'

    # Add/update user_ids field
    user_ids = fields.One2many(
        'sale.commission.plan.user',
        'plan_id',
        string='Assigned Users',
        help='Users who participate in this commission plan with their roles'
    )

    @api.constrains('user_ids')
    def _check_hierarchy_completeness(self):
        """Validate that hierarchy is properly configured"""
        for plan in self:
            if plan.type == 'hierarchical' and plan.user_ids:
                # Check that there's at least one top-level user (no manager)
                top_level_users = plan.user_ids.filtered(lambda u: not u.manager_id)
                if not top_level_users:
                    raise ValidationError(_(
                        'Hierarchical plan must have at least one top-level user '
                        '(user without a manager).'
                    ))
```

---

### 3. Update Hierarchy Traversal Logic

**File:** `belgogreen_sales_commission/models/account_move.py`

**BEFORE (using global res.users role):**
```python
def _get_commission_hierarchy(self, base_user):
    hierarchy = []
    current_user = base_user

    while current_user:
        if current_user.commission_role_id:  # ❌ GLOBAL ROLE
            hierarchy.append((
                current_user,
                current_user.commission_role_id,
                commission_type
            ))
        current_user = current_user.commission_manager_id  # ❌ GLOBAL MANAGER

    return hierarchy
```

**AFTER (using plan-specific role):**
```python
def _get_commission_hierarchy(self, base_user, commission_plan):
    """
    Build hierarchy using plan-specific roles and managers

    Args:
        base_user: The user who made the sale
        commission_plan: The commission plan to use for hierarchy
    """
    hierarchy = []
    current_user = base_user
    seen_ids = set()

    while current_user and current_user.id not in seen_ids:
        # Find user's assignment in THIS plan ✅
        plan_user = self.env['sale.commission.plan.user'].search([
            ('plan_id', '=', commission_plan.id),
            ('user_id', '=', current_user.id)
        ], limit=1)

        if plan_user and plan_user.role_id:
            is_direct_sale = (current_user.id == base_user.id)
            commission_type = 'direct' if is_direct_sale else 'override'

            hierarchy.append((
                current_user,
                plan_user.role_id,  # ✅ PLAN-SPECIFIC ROLE
                commission_type
            ))
            seen_ids.add(current_user.id)

            # Move up to manager IN THIS PLAN ✅
            current_user = plan_user.manager_id
        else:
            # User not in this plan, stop traversal
            break

        # Safety check
        if len(seen_ids) > 20:
            break

    return hierarchy
```

Update the call site:
```python
def _create_commission_for_sale(self, sale_order):
    # ... existing code ...

    # Build hierarchy WITH PLAN ✅
    users_to_commission = self._get_commission_hierarchy(salesperson, commission_plan)

    # ... rest of code ...
```

---

### 4. Update `sale_order.py` Similarly

Same changes needed in:
- `sale_order._get_commission_hierarchy()`
- `sale_order._create_commissions_for_invoice()`

---

### 5. Deprecate (but keep for compatibility) res.users fields

**File:** `belgogreen_sales_commission/models/res_users.py`

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    # DEPRECATED - kept for backward compatibility
    commission_role_id = fields.Many2one(
        'sale.commission.role',
        string='Default Commission Role (DEPRECATED)',
        help='DEPRECATED: Roles are now assigned per commission plan. '
             'This field is kept for backward compatibility only.'
    )

    commission_manager_id = fields.Many2one(
        'res.users',
        string='Default Commission Manager (DEPRECATED)',
        help='DEPRECATED: Managers are now assigned per commission plan. '
             'This field is kept for backward compatibility only.'
    )

    # NEW: Get all plan assignments
    commission_plan_assignments = fields.One2many(
        'sale.commission.plan.user',
        'user_id',
        string='Commission Plan Assignments'
    )
```

---

### 6. Update Security (ir.model.access.csv)

Add new model access:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sale_commission_plan_user_user,sale.commission.plan.user.user,model_sale_commission_plan_user,base.group_user,1,0,0,0
access_sale_commission_plan_user_manager,sale.commission.plan.user.manager,model_sale_commission_plan_user,sales_team.group_sale_manager,1,1,1,1
```

---

### 7. Update Views

**File:** `belgogreen_sales_commission/views/sale_commission_plan_views.xml`

Add tree/form for user assignments inside plan form:
```xml
<page string="Users &amp; Hierarchy" name="users">
    <field name="user_ids">
        <tree editable="bottom">
            <field name="user_id"
                   domain="[('company_id', '=', parent.company_id)]"/>
            <field name="role_id"
                   domain="[('company_id', '=', parent.company_id)]"/>
            <field name="manager_id"/>
            <field name="role_sequence" invisible="1"/>
        </tree>
    </field>

    <!-- Optional: hierarchy diagram -->
    <group string="Hierarchy Preview">
        <field name="user_ids" widget="hierarchy" mode="tree"/>
    </group>
</page>
```

---

### 8. Update __init__.py

Add new model import:
```python
from . import sale_commission_plan_user
```

---

## 🎬 Migration Path

### For Existing Installations

Create migration script: `migrations/19.0.0.1/post-migrate.py`

```python
def migrate(cr, version):
    """Migrate existing user roles to plan-based assignments"""

    # 1. Create plan user records from existing res.users assignments
    cr.execute("""
        INSERT INTO sale_commission_plan_user
            (plan_id, user_id, role_id, manager_id, create_date, write_date)
        SELECT DISTINCT
            p.id as plan_id,
            u.id as user_id,
            u.commission_role_id as role_id,
            u.commission_manager_id as manager_id,
            NOW() as create_date,
            NOW() as write_date
        FROM sale_commission_plan p
        CROSS JOIN res_users u
        WHERE u.commission_role_id IS NOT NULL
            AND p.company_id = u.company_id
            AND p.type = 'hierarchical'
            AND p.state = 'approved'
    """)

    print("✓ Migrated user role assignments to plan-based system")
```

---

## ✅ Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Frederic Adam** | ❌ Can only be in ONE hierarchy | ✅ Can be Directeur in BOTH plans |
| **Multi-company** | ❌ One role across all companies | ✅ Different roles per company/plan |
| **Flexibility** | ❌ Rigid global hierarchy | ✅ Flexible plan-specific hierarchies |
| **Role changes** | ❌ Affects ALL plans | ✅ Only affects specific plan |
| **Complexity** | ✅ Simple (single role) | ⚠️ Moderate (role per plan) |

---

## ⚠️ Potential Issues & Solutions

### Issue 1: Performance
**Problem:** Extra JOIN to get user's role
**Solution:** Index on `sale_commission_plan_user(plan_id, user_id)` + caching

### Issue 2: UI Complexity
**Problem:** More complex setup (assign users to each plan)
**Solution:** Bulk import wizard + templates

### Issue 3: Backward Compatibility
**Problem:** Existing code expects `user.commission_role_id`
**Solution:** Keep deprecated fields, add computed fields that fallback to primary plan

### Issue 4: Circular Hierarchies
**Problem:** User A manages User B in Plan 1, but B manages A in Plan 2
**Solution:** This is ALLOWED (they're different plans). Only prevent cycles within same plan.

---

## 🚀 Implementation Priority

1. **High Priority (Core functionality)**
   - Create `sale.commission.plan.user` model
   - Update hierarchy traversal methods
   - Update security

2. **Medium Priority (UX)**
   - Update plan form view
   - Add bulk assignment wizard
   - Update documentation

3. **Low Priority (Nice to have)**
   - Hierarchy visualization widget
   - Migration script for existing data
   - Deprecation warnings

---

## 📝 Conclusion

**Recommendation:** ✅ **IMPLEMENT THIS REFACTOR**

This architectural change solves fundamental limitations and aligns with best practices for multi-company, multi-plan commission systems. The implementation is straightforward and provides significant business value.

**Estimated Effort:** 2-3 days
- Day 1: Core model and logic changes
- Day 2: Views, security, testing
- Day 3: Migration, documentation, edge cases
