# Supercharged "Données commerciaux" Tab Implementation

## Approach: Conditional Field Display Based on Plan Type

### Implementation Strategy

Instead of creating a separate "Users & Hierarchy" tab, we modify the base module's `user_ids` field display to show different columns based on the plan type.

---

## Option A: Inherit Base Module's user_ids Tree View (Recommended)

### Step 1: Find the Base View ID

First, identify the base module's view structure:
```python
# In Odoo shell or during module load
view = self.env.ref('sale_commission.sale_commission_plan_view_form')
```

### Step 2: Inherit and Extend the Tree View

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>

        <!-- Inherit the base commission plan form and modify user_ids inline tree -->
        <record id="view_sale_commission_plan_form_supercharged" model="ir.ui.view">
            <field name="name">sale.commission.plan.form.supercharged</field>
            <field name="model">sale.commission.plan</field>
            <field name="inherit_id" ref="sale_commission.sale_commission_plan_view_form"/>
            <field name="arch" type="xml">

                <!-- Find the user_ids field and replace its inline tree -->
                <xpath expr="//field[@name='user_ids']" position="replace">
                    <field name="user_ids">
                        <tree editable="bottom">

                            <!-- ALWAYS VISIBLE: User column -->
                            <field name="user_id"
                                   domain="[('company_id', '=', parent.company_id)]"
                                   required="1"/>

                            <!-- HIERARCHICAL ONLY: Role, Manager, Level -->
                            <field name="role_id"
                                   column_invisible="parent.type != 'hierarchical'"
                                   required="parent.type == 'hierarchical'"
                                   domain="[('company_id', '=', parent.company_id)]"
                                   options="{'no_create': True}"/>

                            <field name="manager_id"
                                   column_invisible="parent.type != 'hierarchical'"
                                   domain="[('id', 'in', parent.user_ids.user_id.ids), ('id', '!=', user_id)]"/>

                            <field name="role_sequence"
                                   string="Level"
                                   column_invisible="parent.type != 'hierarchical'"
                                   readonly="1"/>

                            <!-- STANDARD ONLY: Validity dates -->
                            <field name="date_from"
                                   column_invisible="parent.type == 'hierarchical'"
                                   optional="show"/>

                            <field name="date_to"
                                   column_invisible="parent.type == 'hierarchical'"
                                   optional="show"/>

                            <!-- OPTIONAL: Show for both (hidden by default for hierarchical) -->
                            <field name="company_id"
                                   column_invisible="1"/>

                        </tree>
                    </field>
                </xpath>

                <!-- Optional: Add help text that changes based on plan type -->
                <xpath expr="//field[@name='user_ids']" position="after">
                    <group>
                        <div class="alert alert-info"
                             role="alert"
                             invisible="type != 'hierarchical'">
                            <strong>Hierarchical Plan:</strong>
                            <ul>
                                <li>Assign each user with their role (Directeur, Chef d'équipe, Commercial)</li>
                                <li>Set manager relationships within this plan's hierarchy</li>
                                <li>Top-level users should have NO manager</li>
                            </ul>
                        </div>

                        <div class="alert alert-info"
                             role="alert"
                             invisible="type == 'hierarchical'">
                            <strong>Standard Plan:</strong>
                            <ul>
                                <li>Assign users to this commission plan</li>
                                <li>Optionally set validity date ranges (date_from, date_to)</li>
                                <li>Leave dates empty for permanent assignments</li>
                            </ul>
                        </div>
                    </group>
                </xpath>

            </field>
        </record>

    </data>
</odoo>
```

---

## Option B: Use attrs for Dynamic Behavior (More Complex)

If you need even more dynamic behavior:

```xml
<field name="role_id"
       attrs="{'invisible': [('parent.type', '!=', 'hierarchical')],
               'required': [('parent.type', '=', 'hierarchical')],
               'readonly': [('parent.type', '!=', 'hierarchical')]}"/>
```

**Note**: `attrs` is deprecated in Odoo 17+, use `column_invisible` and `required` with domain syntax instead.

---

## Option C: Separate Tree Views by Plan Type

Create two different tree views and dynamically switch:

```xml
<!-- Tree view for standard plans -->
<record id="view_commission_plan_user_tree_standard" model="ir.ui.view">
    <field name="name">sale.commission.plan.user.tree.standard</field>
    <field name="model">sale.commission.plan.user</field>
    <field name="arch" type="xml">
        <tree editable="bottom">
            <field name="user_id"/>
            <field name="date_from"/>
            <field name="date_to"/>
        </tree>
    </field>
</record>

<!-- Tree view for hierarchical plans -->
<record id="view_commission_plan_user_tree_hierarchical" model="ir.ui.view">
    <field name="name">sale.commission.plan.user.tree.hierarchical</field>
    <field name="model">sale.commission.plan.user</field>
    <field name="arch" type="xml">
        <tree editable="bottom">
            <field name="user_id"/>
            <field name="role_id"/>
            <field name="manager_id"/>
            <field name="role_sequence" readonly="1"/>
        </tree>
    </field>
</record>

<!-- In the plan form, use context to select view -->
<field name="user_ids"
       context="{'tree_view_ref': 'belgogreen_sales_commission.view_commission_plan_user_tree_hierarchical' if type == 'hierarchical' else 'belgogreen_sales_commission.view_commission_plan_user_tree_standard'}">
</field>
```

**Note**: Context-based view switching is tricky and may not work reliably in inline trees.

---

## Python Model Adjustments

You may need to add dynamic defaults or validations:

```python
# In sale_commission_plan_user.py

@api.onchange('plan_id')
def _onchange_plan_id(self):
    """Show/hide fields based on plan type"""
    if self.plan_id and self.plan_id.type == 'hierarchical':
        # Clear date fields for hierarchical plans
        self.date_from = False
        self.date_to = False
    else:
        # Clear hierarchy fields for standard plans
        self.role_id = False
        self.manager_id = False

@api.constrains('role_id', 'manager_id', 'plan_id')
def _check_hierarchical_fields(self):
    """Ensure hierarchical fields are only used with hierarchical plans"""
    for rec in self:
        if rec.plan_id.type == 'hierarchical':
            if not rec.role_id:
                raise ValidationError(_('Role is required for hierarchical plans'))
        else:
            if rec.role_id or rec.manager_id:
                raise ValidationError(_('Role and Manager fields are only for hierarchical plans'))
```

---

## Testing Checklist

- [ ] Create standard plan → user_ids shows date_from, date_to only
- [ ] Create hierarchical plan → user_ids shows role, manager, level only
- [ ] Switch plan type from standard to hierarchical → fields update correctly
- [ ] Inline edit works for both plan types
- [ ] Required field validation works correctly
- [ ] Domain filters work (manager domain, role domain)
- [ ] Multi-company: only shows users/roles from same company
- [ ] Cross-plan view: can see user assignments across multiple plans

---

## Migration Notes

If migrating from separate tabs to supercharged tab:

1. **Data**: No changes needed (same model, same fields)
2. **Views**: Remove old "Users & Hierarchy" tab definition
3. **Training**: Update user documentation
4. **Testing**: Verify all existing records display correctly

---

## Rollback Plan

If you need to revert to separate tabs:

1. Keep this supercharged view as `priority="20"` (low priority)
2. Create separate tab with `priority="10"` (high priority)
3. Odoo will use the higher priority view
4. Easy A/B testing

```xml
<record id="view_sale_commission_plan_form_supercharged" model="ir.ui.view">
    <field name="priority">20</field>  <!-- Lower priority = fallback -->
    ...
</record>
```

---

## Performance Considerations

- **Column visibility**: No performance impact (client-side hiding)
- **Domain filters**: Cached, minimal impact
- **Inline editable tree**: Same performance as current implementation

---

## Accessibility

- Screen readers: Will announce visible columns only
- Keyboard navigation: Tab order adapts to visible fields
- Mobile: Fewer columns = better mobile experience

