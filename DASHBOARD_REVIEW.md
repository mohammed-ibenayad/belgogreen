# Commission Dashboard - Complete Review

## Overview
The Commission Dashboard provides a comprehensive view of commission data for salespeople and managers. It displays KPIs, charts, and team metrics.

---

## Dashboard Components

### 1. **KPI Cards (4 Cards)**

#### Card 1: Mes Commissions Totales (My Total Commissions)
**What it shows:**
- Total amount of all commissions for the current user across all time
- Number of pending (unpaid) commissions
- Total count of commission records

**How it's retrieved:**
```python
# From: commission_dashboard.py:96-99
my_commissions = all commissions where user_id = current user
my_total = sum of all commission_amount
my_pending = sum of commission_amount where status = 'unpaid'
my_count = total number of commission records
```

**Data source:** `sale.commission` table filtered by current user

---

#### Card 2: Commissions Payées (Paid Commissions)
**What it shows:**
- Total amount of commissions that have been paid to the user

**How it's retrieved:**
```python
# From: commission_dashboard.py:99
my_paid = sum of commission_amount where status = 'paid' AND user_id = current user
```

**Data source:** `sale.commission` table, filtered by status='paid'

---

#### Card 3: Ce Mois (This Month)
**What it shows:**
- Total commission amount for the current month
- Number of commissions earned this month
- Current month name (e.g., "décembre")

**How it's retrieved:**
```python
# From: commission_dashboard.py:102-111
first_day_month = first day of current month
my_month_comms = commissions where date >= first_day_month AND user_id = current user
my_month_total = sum of commission_amount
my_month_count = count of commissions
current_month_name = formatted month name (using French locale)
```

**Data source:** `sale.commission` table filtered by current month

---

#### Card 4: Commissions d'Équipe (Team Commissions)
**What it shows:**
- Total commissions for all team members (subordinates)
- Number of team members with commissions
- Pending team commissions

**How it's retrieved:**
```python
# From: commission_dashboard.py:32-44, 114-116
# Step 1: Find subordinates
subordinate_assignments = sale.commission.plan.user where manager_id = current user
subordinate_user_ids = list of user_id from subordinate_assignments

# Step 2: Get their commissions
team_commissions = sale.commission where user_id IN subordinate_user_ids
team_total = sum of all team commission_amount
team_pending = sum where status = 'unpaid'
team_members_count = count of unique user_ids
```

**Data source:**
- `sale.commission.plan.user` (to find subordinates)
- `sale.commission` (for subordinate commissions)

**Note:** This card is grayed out if the user has no team (has_team = false)

---

### 2. **Charts Section**

#### Chart 1: Tendance des Commissions (Monthly Trend)
**Type:** Line chart

**What it shows:**
- Commission amounts for each of the last 6 months
- Trend line showing performance over time

**How it's retrieved:**
```python
# From: commission_dashboard.py:145-166
six_months_ago = today - 6 months
For each month from six_months_ago to today:
    month_commissions = sale.commission where:
        - user_id = current user
        - date >= month_start
        - date < month_end

    monthly_data.append({
        'month': formatted month name (e.g., "Dec 2024")
        'amount': sum of commission_amount
        'count': number of commissions
    })
```

**Data source:** `sale.commission` table, grouped by month

---

#### Chart 2: Par Statut (By Status - Histogram)
**Type:** Bar chart (histogram)

**What it shows:**
- Commission amounts grouped by payment status
- 4 status categories: pending, approved, paid, cancelled

**How it's retrieved:**
```python
# From: commission_dashboard.py:168-178
my_commissions = all commissions where user_id = current user

state_distribution = {
    'pending': sum where status = 'unpaid'
    'approved': sum where status = 'claimed'
    'paid': sum where status = 'paid'
    'cancelled': sum where status = 'cancelled'
}
```

**Data source:** `sale.commission` table, grouped by status

**Color coding:**
- Pending: Yellow (#ffc107)
- Approved: Cyan (#17a2b8)
- Paid: Green (#28a745)
- Cancelled: Red (#dc3545)

---

## Data Flow

### Initial Load
1. User opens dashboard → `commission_dashboard.js` mounted
2. JavaScript calls `/commission/dashboard/data` endpoint
3. Controller calls `commission_dashboard.py:get_dashboard_data()`
4. Data retrieved and formatted
5. JavaScript updates UI with KPIs and charts

### Refresh Button ("Actualiser")
When user clicks refresh:
1. JavaScript calls `/commission/dashboard/refresh` endpoint
2. Controller calls `commission_dashboard.py:generate_my_commissions()`
   - This generates NEW commissions from unpaid invoices
   - Returns count and amount of newly created commissions
3. Then calls `get_dashboard_data()` to get updated data
4. JavaScript updates UI
5. Shows notification with generation results

---

## Commission Generation Logic (Refresh Button)

### What happens when you click "Actualiser":

```python
# From: commission_dashboard.py:224-340
1. Check if user is in approved hierarchical plan(s)
2. For each plan the user is assigned to:

   A. DIRECT COMMISSIONS:
      - Find user's own sale orders with paid invoices
      - For each order:
        * Check if legacy commission flags exist (skip if yes)
        * Check if paid invoice exists
        * Check if commission already exists for this invoice
        * Create commission record with commission_type = 'direct'

   B. OVERRIDE COMMISSIONS:
      - Find ALL subordinates in hierarchy (recursive)
      - For each subordinate:
        * Find their sale orders with paid invoices
        * For each order:
          - Check if legacy commission flags exist (skip if yes)
          - Check if paid invoice exists
          - Check if commission already exists
          - Create commission record with commission_type = 'override'
          - Commission is for CURRENT USER, not subordinate

3. Return total count and amount of created commissions
```

### Eligible Orders Criteria:
- Invoice type = 'out_invoice'
- Invoice state = 'posted'
- Payment state = 'paid' or 'in_payment'
- Order state = 'sale' or 'done'
- Order user_id matches target user
- Legacy commission flags are NOT set

### Legacy Flags (Block Commission Generation):
If ANY of these are true on sale order, commission generation is blocked:
- `x_studio_payee_commercial`
- `x_studio_payee_responsable_commercial`
- `x_studio_payee_directeur_commercial`

---

## User Info Section

**Data returned but not displayed visibly:**
```python
user_info = {
    'name': user name
    'role': role name from first active plan assignment
    'manager': manager name from plan assignment
    'has_team': boolean - true if user has subordinates
    'has_active_plan': boolean - true if user is in approved plan
}
```

---

## Access Control

### Dashboard Access
Users without active commission plan assignments won't see the dashboard menu.

**Check:** `commission_dashboard.py:84-92`
```python
user_assignments = sale.commission.plan.user where:
    - user_id = current user
    - plan_id.state = 'approved'

has_active_plan = true if any assignments found
```

If `has_active_plan = false`, dashboard shows access denied message.

---

## Database Tables Used

1. **sale.commission** - Main commission records
   - Fields: commission_amount, status, date, user_id, commission_type

2. **sale.commission.plan.user** - User assignments to plans
   - Fields: user_id, manager_id, plan_id, role_id

3. **sale.order** - Sale orders
   - Fields: user_id, state, invoice_ids, legacy commission flags

4. **account.move** - Invoices
   - Fields: move_type, state, payment_state, invoice_date, amount_total

5. **hr.commission.role.config** - Role configurations
   - Fields: plan_id, role_id, direct_sale_percentage, override_percentage

---

## Key Calculations

### Commission Amount Calculation
```python
# When creating commission (commission_dashboard.py:411-429)
base_amount = invoice.amount_total
commission_percentage = from role_config (direct_sale_percentage or override_percentage)
commission_amount = calculated by sale.commission model using percentage
```

### Team Hierarchy
- Uses recursive function `_get_all_subordinates()` to find ALL subordinates
- Not just direct reports, but entire tree downward
- Prevents circular references with seen_ids tracking
- Maximum depth: 50 levels

---

## Performance Considerations

### Data Retrieval
- All KPIs calculated in single database query per metric
- Charts load data for 6 months only (not all-time)
- Team commissions only calculated if user has subordinates

### Refresh Operation
- Processes ALL user's plans (if assigned to multiple)
- Checks ALL eligible orders for commission creation
- Can create many commissions at once if orders are pending
- Shows count and total amount in notification

---

## Summary of KPI Meanings

| KPI | Meaning | Formula |
|-----|---------|---------|
| My Total | All-time commission earnings | SUM(commission_amount) WHERE user_id = me |
| My Pending | Commissions not yet paid | SUM(commission_amount) WHERE status = 'unpaid' |
| My Paid | Commissions already received | SUM(commission_amount) WHERE status = 'paid' |
| This Month | Current month earnings | SUM(commission_amount) WHERE date >= first_day_month |
| Team Total | All subordinate commissions | SUM(commission_amount) WHERE user_id IN subordinates |
| Team Pending | Subordinate unpaid commissions | SUM(team commission_amount) WHERE status = 'unpaid' |
| Team Members | Number of team members | COUNT(DISTINCT user_id) from team commissions |

---

## Important Notes

1. **Currency Formatting:** Uses company currency settings (symbol, position, decimal places)

2. **Refresh Button:** Does TWO things:
   - Generates new commissions from paid invoices
   - Refreshes dashboard data

3. **Team Card:** Grayed out if user has no subordinates (visual indicator)

4. **Legacy System:** Old commission flags on sale orders prevent new commission generation

5. **Multi-Plan Support:** User can be in multiple plans, commissions generated for each

6. **Deduplication:** System checks for existing commissions before creating (by invoice_id + user_id + role_id + commission_type)
